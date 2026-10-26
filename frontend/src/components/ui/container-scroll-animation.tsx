"use client";
/**
 * ContainerScroll — scroll-driven product-frame section.
 *
 * Adapted from the Aceternity `container-scroll-animation` component:
 * API kept, styling retargeted to the CropSense Minimal system in
 * docs/DESIGN.md (flat white product frame, hairline border, 20px radius),
 * overlap removed so the headline is never clipped, and heights are
 * content-driven instead of fixed.
 */

import { useRef } from "react";
import type { ReactNode } from "react";
import { motion, useScroll, useTransform } from "framer-motion";
import type { MotionValue } from "framer-motion";

export const ContainerScroll = ({
  titleComponent,
  children,
}: {
  titleComponent: string | ReactNode;
  children: ReactNode;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: containerRef,
  });

  const rotate = useTransform(scrollYProgress, [0, 1], [6, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], [1.04, 1]);
  const translate = useTransform(scrollYProgress, [0, 1], [0, -12]);

  return (
    <div
      className="relative flex items-center justify-center p-2 py-16 md:py-24"
      ref={containerRef}
    >
      <div
        className="w-full relative"
        style={{
          perspective: "1200px",
        }}
      >
        <Header translate={translate} titleComponent={titleComponent} />
        <Card rotate={rotate} scale={scale}>
          {children}
        </Card>
      </div>
    </div>
  );
};

export const Header = ({
  translate,
  titleComponent,
}: {
  translate: MotionValue<number>;
  titleComponent: string | ReactNode;
}) => {
  return (
    <motion.div
      style={{
        translateY: translate,
      }}
      className="relative z-10 max-w-4xl mx-auto mb-10 md:mb-14"
    >
      {titleComponent}
    </motion.div>
  );
};

export const Card = ({
  rotate,
  scale,
  children,
}: {
  rotate: MotionValue<number>;
  scale: MotionValue<number>;
  children: ReactNode;
}) => {
  return (
    <motion.div
      style={{
        rotateX: rotate,
        scale,
      }}
      className="max-w-5xl mx-auto w-full border border-hairline bg-surface p-2 rounded-[20px] shadow-[0_24px_60px_rgba(6,71,52,0.12)]"
    >
      <div className="w-full overflow-hidden rounded-xl bg-page">
        {/* browser chrome — the frame reads as the real product, not an empty box */}
        <div className="flex items-center justify-between border-b border-hairline bg-surface px-4 py-2.5">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            <span className="size-2 rounded-full bg-forest/25" />
            <span className="size-2 rounded-full bg-forest/25" />
            <span className="size-2 rounded-full bg-forest/25" />
          </div>
          <span className="rounded-full bg-page px-3 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
            zenvy.app/field-lab
          </span>
          <span className="flex items-center gap-1.5" aria-hidden="true">
            <span className="size-2 rounded-full bg-forest/15" />
            <span className="size-2 rounded-full bg-forest/15" />
          </span>
        </div>
        <div className="p-3 md:p-6">{children}</div>
      </div>
    </motion.div>
  );
};
