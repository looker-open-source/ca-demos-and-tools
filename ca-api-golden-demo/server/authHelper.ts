import { GoogleAuth } from "google-auth-library";

export async function getAccessToken() {
  const auth = new GoogleAuth({
    scopes: "https://www.googleapis.com/auth/cloud-platform",
  });

  let projectId = process.env.GOOGLE_CLOUD_PROJECT;

  if (!projectId) {
    projectId = await auth.getProjectId();
  }

  const client = await auth.getClient();
  const token = (await client.getAccessToken()).token;
  return { token, projectId };
}
