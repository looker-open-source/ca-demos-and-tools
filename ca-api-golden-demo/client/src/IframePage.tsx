import React from "react";

const IframePage: React.FC = () => {
  return (
    <iframe
      src={process.env.REACT_APP_LOOKER_STUDIO_REPORT}
      style={{
        width: "100%",
        height: "100vh",
        border: "none",
        margin: 0,
        padding: 0,
        display: "block",
      }}
      title="Studio in Looker Report"
    />
  );
};

export default IframePage;
