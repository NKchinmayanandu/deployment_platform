// Deployment status enum matching backend
export type DeploymentStatus =
  | 'QUEUED'
  | 'DEPLOYING'
  | 'RUNNING'
  | 'STOPPED'
  | 'FAILED'
  | 'RESTARTING'
  | 'STARTING'
  | 'REMOVED';

export interface Application {
  id: number;
  owner_id: number;
  name: string;
  image_name: string;
  created_at: string;
}

export interface DeploymentStatusResponse {
  status: DeploymentStatus;
  url: string | null;
  host_port: number | null;
}

export interface User {
  id: number;
  email: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface ApplicationCreate {
  name: string;
  image_name: string;
}
