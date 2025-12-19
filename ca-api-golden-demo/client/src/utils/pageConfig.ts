export interface PageConfig {
  logo: string;
  title: string;
  avatar: string;
  bodyBackground: string;
  userQuestionBackground: string;
  userQuestionText: string;
  newConversationButtonBackground: string;
  newConversationButtonColor: string;
}

export const CUSTOM_VARS = [
  "bodyBackground",
  "userQuestionBackground",
  "userQuestionText",
  "newConversationButtonBackground",
  "newConversationButtonColor",
] as const;

export const PAGE_ID_MAP: Record<string, PageConfig> = {
  // used for multimodal pages
  default: {
    logo: "/cymbalpets_horizontal_logo.png",
    avatar: "/cymbalpets_paw.png",
    title: "Global Pets Data Agent",
    bodyBackground: "#000000",
    userQuestionBackground: "#a3fd8c",
    userQuestionText: "#202124",
    newConversationButtonBackground: "#1a7344",
    newConversationButtonColor: "#ffffff",
  },
  openaq: {
    logo: "not-in-use",
    avatar: "/gemini.png",
    title: "not-in-use",
    bodyBackground: "not-in-use",
    userQuestionBackground: "not-in-use",
    userQuestionText: "not-in-use",
    newConversationButtonBackground: "not-in-use",
    newConversationButtonColor: "not-in-use",
  },
  thelook: {
    logo: "not-in-use",
    avatar: "/gemini.png",
    title: "not-in-use",
    bodyBackground: "not-in-use",
    userQuestionBackground: "not-in-use",
    userQuestionText: "not-in-use",
    newConversationButtonBackground: "not-in-use",
    newConversationButtonColor: "not-in-use",
  },
  gemini: {
    logo: "not-in-use",
    avatar: "/gemini.png",
    title: "not-in-use",
    bodyBackground: "not-in-use",
    userQuestionBackground: "not-in-use",
    userQuestionText: "not-in-use",
    newConversationButtonBackground: "not-in-use",
    newConversationButtonColor: "not-in-use",
  },
  cymbalpets: {
    logo: "/cymbalpets_horizontal_logo.png",
    avatar: "/cymbalpets.png",
    title: "Global Pets Data Agent",
    bodyBackground: "#000000",
    userQuestionBackground: "#a3fd8c",
    userQuestionText: "#202124",
    newConversationButtonBackground: "#1a7344",
    newConversationButtonColor: "#ffffff",
  },
  cymbalpets_branded: {
    logo: "/cymbalpets_horizontal_logo.png",
    avatar: "/cymbalpets.png",
    title: "Global Pets Data Agent",
    bodyBackground: "#000000",
    userQuestionBackground: "#a3fd8c",
    userQuestionText: "#202124",
    newConversationButtonBackground: "#1a7344",
    newConversationButtonColor: "#ffffff",
  },
  cymbalpets_embed: {
    logo: "/cymbalpets_horizontal_logo.png",
    avatar: "/cymbalpets.png",
    title: "Global Pets Data Agent",
    bodyBackground: "#000000",
    userQuestionBackground: "#a3fd8c",
    userQuestionText: "#202124",
    newConversationButtonBackground: "#1a7344",
    newConversationButtonColor: "#ffffff",
  },
  globalgadgets_embed: {
    logo: "/globalgadgets_logo.png",
    avatar: "/globalgadgets_avatar.png",
    title: "Global Gadgets Data Agent",
    bodyBackground: "#2f4a7d",
    userQuestionBackground: "#cbd6e5",
    userQuestionText: "#202124",
    newConversationButtonBackground: "#748fb0",
    newConversationButtonColor: "#ffffff",
  },
};
