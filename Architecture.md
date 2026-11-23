Architecture
1. System overview
This project is a self-hosted deployment platform. The API accepts
deployment requests, persists deployment metadata, and delegates
container lifecycle work to a background worker. Docker is the execution
layer: deployed applications run as containers managed by the platform.

The main components are:
- FastAPI backend --- authentication, deployment API, lifecycle
  requests, status and log endpoints.
- ARQ worker --- executes asynchronous/background deployment jobs
  using Redis as its queue backend.
- PostgreSQL --- persistent application data, including users and
  deployment records.
- Redis --- background-job queue and supporting coordination/cache
  functionality.
- Docker Engine --- pulls images, creates and manages deployed
  application containers.
- Traefik --- reverse proxy and dynamic router for the API and
  deployed applications.
- Cloudflare Tunnel (cloudflared) --- exposes the relevant
  services through Cloudflare without requiring direct inbound access
  to the host.
This document records the architecture understood from the current
implementation discussions. Exact ports, network names, environment
variables, and deployment-specific details should be checked against the
Compose files and application configuration.
2. Runtime topology
                         Internet
                            |
                     Cloudflare DNS
                            |
                     Cloudflare Tunnel
                       cloudflared
                            |
                         Traefik
                      reverse proxy
                       /         \
              API hostname     App hostnames
                   |                |
             FastAPI API       User containers
                   |
          PostgreSQL / Redis
                   |
             Redis-backed
               ARQ queue
                   |
               ARQ worker
                   |
               Docker Engine
                   |
           Deployed containers
The API and worker are separate processes with different
responsibilities. They may currently be packaged into the same platform
container, while the application containers they create are separate
Docker containers.
3. Backend and ARQ worker
FastAPI backend
The backend is the control plane's HTTP interface. It handles incoming
client requests such as authentication, creating deployments, and
requesting lifecycle operations. It validates requests, interacts with
PostgreSQL, and enqueues work that should happen asynchronously.

The API should not need to hold an HTTP request open while a potentially
slow operation such as pulling an image or starting a container
completes. Instead, it can enqueue a job and let the worker perform that
work.
ARQ worker
ARQ is the background job processor. It consumes jobs from Redis and
performs asynchronous tasks such as pulling an image, creating a
container, starting or stopping it, and updating deployment state.

Redis provides the queue boundary between the API process and worker
process. This decouples request handling from longer-running
infrastructure operations.
Why run both processes under Supervisor?
The platform container currently uses Supervisor to manage two
long-running processes:
1. The FastAPI application server.
2. The ARQ worker process.
They are separate processes because they have different jobs and
lifecycles: FastAPI serves HTTP requests, while ARQ consumes background
jobs. Supervisor is the process manager inside that container. It starts
both processes, monitors them, and can restart a process if it exits
unexpectedly.

This is a packaging/deployment choice, not a requirement of FastAPI or
ARQ. Running both in one container keeps the initial deployment simpler,
but it also couples their scaling and failure boundary: restarting or
replacing that container affects both processes. A later architecture
could place the API and worker in separate Compose services while
keeping them in the same application codebase and sharing Redis,
PostgreSQL, and the Docker socket as required.

There is no need for two Supervisor daemons. The intended arrangement is
one Supervisor instance managing two child processes, typically defined
as separate [program:...] entries in its configuration.
4. Docker integration
The platform uses the Docker Engine to manage deployed application
containers. The platform backend/worker communicates with the Docker
daemon through the Docker socket mounted into the platform container:
/var/run/docker.sock:/var/run/docker.sock
This gives the platform process access to Docker operations on the host,
such as pulling images, creating containers,
starting/stopping/restarting them, inspecting state, and retrieving
logs.

The Docker socket is highly privileged: a process with access to it can
generally control the host's containers and may be able to gain
host-level control. It should only be mounted into trusted platform
components and protected accordingly.

The platform's own container and the user application containers are
distinct. The platform container runs the control-plane API/worker;
deployed containers run the workloads submitted by users.
5. Traefik routing and Docker labels
Traefik acts as the reverse proxy. It watches Docker for containers and
reads their labels to discover which containers should receive traffic
and how that traffic should be routed.

Labels are metadata attached to a container by Docker Compose. They tell
Traefik things such as:
- Whether Traefik should consider the container
  (traefik.enable=true).
- Which hostname a router should match
  (traefik.http.routers.<router>.rule).
- Which entrypoint the router should use.
- Which Traefik service the router should forward to.
- Which internal container port the service should target.
A router matches an incoming request; a Traefik service represents the
backend destination. These are separate concepts. When a container
exposes multiple Traefik services, explicitly associate each router with
its intended service using the router's .service label. Otherwise,
Traefik may report that it cannot automatically link a router when
multiple services are available.

For the platform API, the API hostname routes to the platform backend.
For deployed applications, each application container can carry its own
routing labels so Traefik can discover it and route its assigned
hostname to the application's internal port.
6. Cloudflare Tunnel
cloudflared establishes the outbound tunnel from the host to
Cloudflare. Cloudflare DNS directs public hostnames through that tunnel,
and traffic is forwarded to the configured local ingress endpoint
(Traefik in this architecture).

The tunnel provides public reachability without requiring the host to
expose the application ports directly to the Internet. Traefik remains
responsible for hostname-based routing behind the tunnel.
7. PostgreSQL and Redis
- PostgreSQL is the durable source of truth for application
  records, including deployment metadata and state.
- Redis is used by ARQ as the job queue backend. It can also
  support other short-lived coordination or caching needs where
  implemented.
The API writes durable state to PostgreSQL and submits background work
to Redis. The worker performs the operation through Docker and updates
the corresponding database state.
8. Compose environments
The project uses a base production Compose file and a development
override file.
- docker-compose.yml contains the base/production service
  definitions and shared infrastructure configuration.
- docker-compose.dev.yml is supplied after the base file when
  starting development. It overrides the backend service's
  development-specific settings while inheriting services such as
  Traefik and cloudflared from the base configuration.
Example:
# Production configuration
docker compose up -d --build

# Merged development configuration
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# Stop the merged development project
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
Compose merges files by service name. To override the production
backend, both files must call that service backend. Giving the
development service a different name such as backend-dev creates a
second service instead of overriding the first.

Compose also merges individual fields according to their merge rules. In
particular, labels can be merged by key. If development must replace all
production Traefik labels rather than retain both sets, use Compose's
!override tag for the development labels field (supported by modern
Docker Compose versions).

Always use the same file order for config, up, and down, because
later files override earlier files. The merged development configuration
manages the services in the base file too; it is not an isolated
backend-only project. Starting or stopping that merged project can
therefore affect shared infrastructure and the backend service in that
project. Do not assume production and development backends can run
simultaneously under the same Compose project.
9. Key request and deployment flow
1. A client sends a deployment request to the FastAPI backend.
2. The backend authenticates and validates the request.
3. The backend stores or updates deployment metadata in PostgreSQL.
4. The backend enqueues the deployment task in Redis.
5. The ARQ worker consumes the task.
6. The worker uses the Docker Engine to pull the requested image and
   create/start the application container.
7. The worker updates deployment state in PostgreSQL.
8. Traefik discovers the application container through its Docker
   labels and routes matching hostnames to it.
9. Public traffic reaches the host through Cloudflare Tunnel and is
   forwarded to Traefik.
10. Architectural boundaries and operational cautions
- API vs worker: HTTP request handling and long-running deployment
  operations are separate processes, even if Supervisor currently runs
  them in one container.
- Queue vs database: Redis transports background jobs; PostgreSQL
  stores durable application state.
- Control plane vs workloads: The platform backend/worker manages
  containers; user applications run in their own containers.
- Ingress vs application: Cloudflare Tunnel provides the external
  path, while Traefik performs internal host-based routing.
- Docker socket security: Access to the Docker socket is
  privileged and must be restricted.
- Compose merge behavior: Validate the effective configuration
  before applying changes:
docker compose -f docker-compose.yml -f docker-compose.dev.yml config
This is especially important for labels, ports, volumes, commands, and
networks.