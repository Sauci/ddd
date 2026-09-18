import { Banner } from "./Banner";

export default { title: "UI / Banner" };

// Named Stopped/NoDictionary rather than the brief's Error/Warning: Biome's noShadowRestrictedNames
// refuses a story named Error, which shadows the global.
export const Stopped = () => (
  <Banner tone="error">ddd gui has stopped. Start it again and open the address it prints.</Banner>
);

export const NoDictionary = () => (
  <Banner tone="warning">
    This project has no dictionary, so its modules are drawn without arrows.
  </Banner>
);
