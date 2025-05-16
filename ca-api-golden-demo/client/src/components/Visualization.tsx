import React, { useEffect, useRef } from "react";
import embed from "vega-embed";

interface VisualizationProps {
  spec: any;
}

const Visualization: React.FC<VisualizationProps> = ({ spec }) => {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (spec && chartRef.current) {
      const updatedSpec = { ...spec, width: "container" };
      embed(chartRef.current, updatedSpec).catch((error) =>
        console.error(error)
      );
    }
  }, [spec]);

  return (
    <div className="vega-chart-wrapper">
      <div ref={chartRef} className="vega-chart-inner" />
    </div>
  );
};

export default Visualization;
