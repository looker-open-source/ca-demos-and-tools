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
