import { GoogleSignInButton } from "../../../shared/auth/GoogleSignInButton";

/** Console keeps the dark ("filled_black") Google button. */
export function GoogleButton(props: {
  clientId: string;
  onCredential: (idToken: string) => void;
  onLoadError: (message: string) => void;
}) {
  return <GoogleSignInButton {...props} theme="filled_black" />;
}
