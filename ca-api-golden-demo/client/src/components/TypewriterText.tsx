import React from "react";

interface TypewriterTextProps {
  text: string;
  delayMultiplier?: number;
  containerClassName?: string;
  paragraphClassName?: string;
  spanClassName?: string;
}

const TypewriterText: React.FC<TypewriterTextProps> = ({
  text,
  delayMultiplier = 0.02,
  containerClassName = "",
  paragraphClassName = "",
  spanClassName = "",
}) => {
  return (
    <div className={containerClassName}>
      <p className={paragraphClassName}>
        {text.split("").map((char, index) => (
          <span
            key={index}
            className={spanClassName}
            style={{ animationDelay: `${index * delayMultiplier}s` }}
          >
            {char}
          </span>
        ))}
      </p>
    </div>
  );
};

export default TypewriterText;
