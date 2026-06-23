/** Wire shape of `POST /v1/auth/oauth/google` (the FastAPI token envelope). Shared
 *  by the session factory across surfaces. `applicant_id` is null for recruiter/admin. */
export interface GoogleOAuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    id: string;
    email: string;
    role: string;
    applicant_id: string | null;
    is_new_user: boolean;
  };
}
