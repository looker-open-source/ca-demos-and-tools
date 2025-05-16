import { signInWithPopup } from "firebase/auth";
import { auth, provider } from "./utils/firebase";

function LoginPage() {
  const handleSignIn = async () => {
    try {
      await signInWithPopup(auth, provider);
    } catch (error) {
      console.error("Sign in error:", error);
      alert("An error occurred during sign in.");
    }
  };

  return (
    <div>
      <button onClick={handleSignIn}>Sign In with Google</button>
    </div>
  );
}

export default LoginPage;
