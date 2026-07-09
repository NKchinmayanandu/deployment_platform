from app.infrastructure.docker_client import client
from app.cache.port_allocation import get_next_port
import asyncio
import docker
import subprocess
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

async def run_deployment_logic(app_id:int,image_name:str):
    container_name = f"app_{app_id}_{image_name.replace(':','_')}"
    port = get_next_port()
    subprocess.run(["docker","pull",image_name],check=True,capture_output=True)

    CMD = ["docker","run","-d","--name",
               container_name,"-p",f"{port}:80",image_name]
    
    subprocess.run(CMD,check=True,capture_output=True)

    return None
    