// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

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
