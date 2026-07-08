from app.infrastructure.docker_client import client
import asyncio
import docker
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