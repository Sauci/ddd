import type { Route } from "../lib/route";
import type { LoadBanner } from "../lib/unloaded";
import { Banner } from "../ui/Banner";
import { Sentence } from "../ui/Sentence";

/** The banner under the masthead of every page of the open project (16:I9): why the last analysis
 * failed, the files that did not load, each leading to its finding, and the build records this DDD
 * cannot use - a line each, as `loadBanner` (lib/unloaded.ts) says them. A picture of its props. */
export function LoadBannerView({
  banner,
  onFollow,
}: {
  banner: LoadBanner;
  onFollow: (to: Route) => void;
}) {
  return (
    <Banner tone={banner.tone}>
      {banner.lines.map((line, index) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: a line is its own position in the banner
        <p key={index} className="banner-line">
          <Sentence parts={line} onFollow={onFollow} />
        </p>
      ))}
    </Banner>
  );
}
