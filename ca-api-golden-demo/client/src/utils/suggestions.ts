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

export interface Suggestion {
  dataset: string;
  formattedName: string;
  questions: string[];
}

export const suggestions: Suggestion[] = [
  {
    dataset: "openaq",
    formattedName: "OpenAQ",
    questions: [
      "What are the most common types of pollutants?",
      "Which city has the highest average ozone?",
      "How many measurements do you have in each country?",
    ],
  },
  {
    dataset: "thelook",
    formattedName: "The Look",
    questions: [
      "What are the most common traffic sources?",
      "Show me orders by country for last year",
      "How do traffic sources compare by week for 2023 vs 2024 in the US?",
    ],
  },
  {
    dataset: "cymbalpets",
    formattedName: "Cymbal Pets",
    questions: [
      "Where are my biggest customers located?",
      "How do my online and offline sales compare by month for the last year?",
      "Which brands have the most sales last month? Display as a pie chart",
    ],
  },
  {
    dataset: "cymbalpets_branded",
    formattedName: "Cymbal Pets",
    questions: [
      "Where are my biggest customers located?",
      "How do my online and offline sales compare by month for the last year?",
      "Which brands have the most sales last month? Display as a pie chart",
    ],
  },
  {
    dataset: "cymbalpets_embed_business_pulse",
    formattedName: "Cymbal Pets",
    questions: [
      "Where are my biggest customers located?",
      "How do my online and offline sales compare by month for the last year?",
      "Which brands have the most sales last month? Display as a pie chart",
    ],
  },
  {
    dataset: "cymbalpets_embed_supplier_metrics",
    formattedName: "Cymbal Pets",
    questions: [
      "Show the average lead time per supplier state as a map",
      "How does average lead time per my top 3 suppliers compare by month for the last year?",
      "Show me total sales per suppliers for the last month. Display as bar chart",
    ],
  },
];
