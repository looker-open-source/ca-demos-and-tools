import React, { useEffect, useState } from "react";
import { useUser } from "./UserContext";

interface AllowlistWrapperProps {
  pageId: string;
  children: React.ReactNode;
}

const AllowlistWrapper: React.FC<AllowlistWrapperProps> = ({
  pageId,
  children,
}) => {
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const { user } = useUser();

  useEffect(() => {
    if (!user) return;

    async function checkAllowlist() {
      try {
        const response = await fetch(`/api/allowlist?pageId=${pageId}`);
        const data = await response.json();
        if (response.ok) {
          if (data.allowlist && data.allowlist.includes(user!.email)) {
            setAllowed(true);
          } else {
            setAllowed(false);
          }
        } else {
          console.error("Error fetching allowlist:", data.error);
          setAllowed(false);
        }
      } catch (error) {
        console.error("Error fetching allowlist:", error);
        setAllowed(false);
      } finally {
        setLoading(false);
      }
    }

    checkAllowlist();
  }, [user, pageId]);

  if (loading || allowed === null) {
    return <div>Loading...</div>;
  }

  if (!allowed) {
    return (
      <div>
        <p style={{ color: "white", fontSize: "24px" }}>
          <strong>Access Denied</strong>
          <br />
          <br />
          Direct access to this shared demo is limited due to concurrent session
          limits with the Gemini Live API.
          <br />
          <br />
          To run the demo, please deploy your own app in Argolis using the
          developer kit. Deployment instructions can be found at{" "}
          <a
            href="http://go/ca-api-golden-demo-devkit"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: "#8ab4f8" }}
          >
            <strong>go/ca-api-golden-demo-devkit</strong>
          </a>
          .
          <br />
          <br />
          For questions or issues with the deployment, contact{" "}
          <a
            href="mailto:cloud-bi-opm-demos@google.com"
            style={{ color: "#8ab4f8" }}
          >
            <strong>cloud-bi-opm-demos@google.com</strong>
          </a>
          .
        </p>
      </div>
    );
  }

  return <>{children}</>;
};

export default AllowlistWrapper;
