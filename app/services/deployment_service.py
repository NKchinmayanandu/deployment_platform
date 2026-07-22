from app.infrastructure.docker_client import client
from app.cache.port_allocation import get_next_port
import asyncio
import docker
from app.db.session import AsyncSessionLocal
from app.repositories.get_deployment import deployment_get
import logging


import asyncio
import logging

async def run_deployment_logic(deployment_id: int, image_name: str, env: dict, container_port: int):
    container_name = f"app-{deployment_id}"
    container = None
    try:
        port = await get_next_port()
        await asyncio.to_thread(client.images.pull, image_name)
        container = await asyncio.to_thread(
            client.containers.run,
            image_name,
            detach=True,
            name=container_name,
            labels = {
                    "traefik.enable": "true",
                    f"traefik.http.routers.{container_name}.rule":
                        f"Host(`{container_name}.deploy.thechinmay.in`)",

                    f"traefik.http.services.{container_name}.loadbalancer.server.port":
                        str(container_port),
                },
            extra_hosts={
                "host.docker.internal": "host-gateway"
            },
            ports={f"{container_port}/tcp": port},
            environment=env
        )
        max_retries = 3
        db_success = False
        
        for attempt in range(1, max_retries + 1):
            try:
                async with AsyncSessionLocal() as db:
                    deployment = await deployment_get(deployment_id, db)
                    deployment.container_name = container.name
                    deployment.container_id = container.id
                    deployment.host_port = port
                    deployment.deployment_url = f"https://{container_name}.deploy.thechinmay.in"
                    await db.commit()
                
                db_success = True
                break 
                
            except Exception as db_error:
                logging.warning(f"DB update attempt {attempt}/{max_retries} failed: {db_error}")
                if attempt == max_retries:
                    raise  
                await asyncio.sleep(1)
                
        if db_success:
            logging.info("Deployment committed to the db successfully")
            return None

    except Exception as e:
        logging.exception("Deployment failed completely after retries. Cleaning up container...")
        if container is not None:
            try:
                await asyncio.to_thread(container.remove, force=True)
                logging.info(f"Cleaned up unused container: {container_name}")
            except Exception as cleanup_error:
                logging.error(f"Failed to cleanup container {container_name}: {cleanup_error}")
                
        raise
    

from docker.errors import NotFound


async def start_container(container_name: str) -> tuple[bool, str]:
    try:
        container = await asyncio.to_thread(client.containers.get, container_name)
        await asyncio.to_thread(container.reload)

        if container.status == "running":
            return True, "already_running"

        await asyncio.to_thread(container.start)
        return True, "started"

    except NotFound:
        return False, "not_found"
    except Exception as e:
        logging.exception(f"Failed to start {container_name}: {e}")
        raise


async def remove_container(container_name: str) -> tuple[bool, str]:
    try:
        container = await asyncio.to_thread(client.containers.get, container_name)
        await asyncio.to_thread(container.remove, force=True)
        return True, "removed"

    except NotFound:
        logging.info(f"Container {container_name} not found during remove, skipping.")
        return False, "not_found"
    except Exception as e:
        logging.exception(f"Failed to remove {container_name}: {e}")
        raise

async def stop_deployed_container(container_name: str) -> bool:
    try:
        container = client.containers.get(container_name)

        await asyncio.to_thread(container.reload)

        if container.status == "exited":
            return True

        await asyncio.to_thread(container.stop)
        return True

    except NotFound:
        return False

async def restart_container(container_name:str) -> bool:
    try:
        container = client.containers.get(container_name)

        await asyncio.to_thread(container.restart)
        return True
    except NotFound:
        return False
    except Exception as e:
        logging.exception(f"Failed to restart {container_name}: {e}")
        return False