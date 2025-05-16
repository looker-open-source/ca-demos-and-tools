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

  // TODO - parameterise email
  if (!allowed) {
    return (
      <div>
        <p style={{ color: "white", fontSize: "24px" }}>
          Access Denied - Reach out to cloud-bi-opm-demos@google.com if you
          require access
        </p>
      </div>
    );
  }

  return <>{children}</>;
};

export default AllowlistWrapper;
