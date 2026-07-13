from app.infrastructure.docker_client import client
from app.cache.port_allocation import get_next_port
import asyncio
import docker
from app.db.session import AsyncSessionLocal
from app.models.deployment import Deployment
from app.repositories.get_deployment import deployment_get
async def delete_application_container(container_name:str):
    loop = asyncio.get_event_loop()
    def _delete():
        try:
            container = client.containers.get(container_name)
            container.remove(force=True)
        except docker.errors.NotFound:
            print(f"Container {container_name} not found, skipping.")
        except Exception as e:
            print(f"Error deleting container {container_name}: {e}")
            raise e

    # Run the synchronous docker call in a separate thread
    await loop.run_in_executor(None, _delete)

async def run_deployment_logic(deployment_id:int,image_name:str):
    container_name = f"app-{deployment_id}"
    port = await get_next_port()
    await asyncio.to_thread(client.images.pull,image_name,)
    container = await asyncio.to_thread(client.containers.run,
                                        image_name,
                                        detach=True,
                                        name=container_name,
                                        ports={"80/tcp":port})
    async with AsyncSessionLocal() as db:
        deployment = await deployment_get(deployment_id, db)
        deployment.container_name = container.name
        deployment.container_id = container.id
        deployment.host_port = port
        await db.commit()

    return None

from docker.errors import NotFound

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
        print(f"Failed to restart {container_name}: {e}")
        return False