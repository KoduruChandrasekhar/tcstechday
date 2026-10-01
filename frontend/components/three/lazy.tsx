"use client";
// 3D views load on the client only, after the page shell, so tables and figures appear first.
import dynamic from "next/dynamic";

const wait = () => <div className="stage-fallback">Loading 3D view</div>;
export const NetworkMap = dynamic(() => import("./NetworkMap"), { ssr: false, loading: wait });
export const StockRunway = dynamic(() => import("./StockRunway"), { ssr: false, loading: wait });
export const SegmentBlocks = dynamic(() => import("./SegmentBlocks"), { ssr: false, loading: wait });
