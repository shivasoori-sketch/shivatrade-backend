import ThesisCard from "./ThesisCard.jsx";
import {
  applyDemoNoIndex,
  DEMO_BANNER,
  DEMO_SCENARIOS,
  demoModeFromPage,
} from "./demoScenario.js";
import { useEffect } from "react";

export default function DemoThesisMount() {
  const demoMode = demoModeFromPage();
  const demoFixture = demoMode ? DEMO_SCENARIOS[demoMode] : null;

  useEffect(() => {
    applyDemoNoIndex();
  }, [demoMode]);

  if (!demoFixture) {
    return (
      <ThesisCard
        idle
        idleMessage="Unknown demo mode. Use ?demo=holds, weakening, or invalidated."
      />
    );
  }

  return (
    <ThesisCard
      idle={false}
      isDemo
      trade={demoFixture.trade}
      state={demoFixture.state}
      book={demoFixture.book}
      showBookLine
      lastUpdated={Date.now()}
      timeInTradeLabel={demoFixture.timeInTradeLabel}
      adversePts={demoFixture.adversePts}
      demoBanner={DEMO_BANNER}
    />
  );
}
