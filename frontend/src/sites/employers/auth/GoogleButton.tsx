import { GoogleSignInButton } from "../../../shared/auth/GoogleSignInButton";

/** Employers keeps the brand-blue Google button — the interactive colour used
 *  for primary actions across every surface. */
export function GoogleButton(props: {
  clientId: string;
  onCredential: (idToken: string) => void;
  onLoadError: (message: string) => void;
}) {
  return <GoogleSignInButton {...props} theme="filled_blue" />;
}
