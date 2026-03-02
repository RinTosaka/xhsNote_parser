import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, fetchOutputs, parseBatch, parseSingle } from "./api";
import type {
  BatchItem,
  OutputItem,
  ParseOptions,
  ParseResponse,
} from "./types";
import { createZip } from "./zip";

type Mode = "single" | "batch";

type ResultCard = {
  id: string;
  url: string;
  ok: boolean;
  createdAt: string;
  options?: ParseOptions;
  response?: ParseResponse;
  error?: string;
};

type PreviewItem = {
  type: "image" | "video";
  url: string;
  poster?: string;
  title: string;
  loop?: boolean;
  muted?: boolean;
};

const HISTORY_KEY = "xhsnote.history";

const buildId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
};

const formatNumber = (value: unknown): string => {
  if (typeof value === "number") {
    return value.toLocaleString();
  }
  if (typeof value === "string" && value.trim()) {
    const number = Number(value);
    if (!Number.isNaN(number)) {
      return number.toLocaleString();
    }
  }
  if (value === null || value === undefined) {
    return "-";
  }
  return String(value);
};

const stringifyJson = (payload: unknown) => JSON.stringify(payload, null, 2);

const parseList = (raw: string) =>
  raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

const EXAMPLE_URL =
  "https://www.xiaohongshu.com/explore/6971ebf3000000002202076e?xsec_token=AB7yCpkwh6ZRTGkPFLvJcq_9_L0Nri570NCfUkPUFPCl8=&xsec_source=pc_user";

const normalizeMediaUrl = (url: string): string => {
  const trimmed = url.trim();
  if (!trimmed) {
    return trimmed;
  }
  if (trimmed.startsWith("//")) {
    return `https:${trimmed}`;
  }
  if (trimmed.startsWith("http://")) {
    return `https://${trimmed.slice("http://".length)}`;
  }
  return trimmed;
};

const normalizeProxyTargetUrl = (url: string): string => {
  const trimmed = url.trim();
  if (!trimmed) {
    return trimmed;
  }
  if (trimmed.startsWith("//")) {
    return `https:${trimmed}`;
  }
  return trimmed;
};

const toMediaProxyUrl = (url: string): string =>
  `${API_BASE}/media?url=${encodeURIComponent(normalizeProxyTargetUrl(url))}`;

const getCoverUrl = (note: Record<string, any>, images: any[]) =>
  normalizeMediaUrl(
    note?.cover?.urlNoWatermark ||
      note?.cover?.urlDefault ||
      note?.cover?.url ||
      images?.[0]?.urlNoWatermark ||
      images?.[0]?.urlDefault ||
      images?.[0]?.url ||
      ""
  );

const getImageUrl = (image: any) =>
  normalizeMediaUrl(image?.urlNoWatermark || image?.urlDefault || image?.url || "");

const extractLiveUrl = (image: any) => {
  if (!image || typeof image !== "object") {
    return null;
  }
  const extractFromStream = (stream: any) => {
    if (!stream || typeof stream !== "object") {
      return null;
    }
    for (const key of ["h264", "h265", "av1", "h266"]) {
      const entries = stream[key];
      if (!Array.isArray(entries) || !entries.length) {
        continue;
      }
      const first = entries[0];
      if (!first || typeof first !== "object") {
        continue;
      }
      if (typeof first.masterUrl === "string" && first.masterUrl) {
        return normalizeProxyTargetUrl(first.masterUrl);
      }
      const backups = first.backupUrls;
      if (Array.isArray(backups) && typeof backups[0] === "string" && backups[0]) {
        return normalizeProxyTargetUrl(backups[0]);
      }
    }
    return null;
  };

  const directKeys = [
    "livePhotoUrl",
    "livePhotoURL",
    "livePhotoUrlDefault",
    "livePhotoPlayUrl",
    "livePhotoVideoUrl",
  ];
  for (const key of directKeys) {
    if (typeof image[key] === "string" && image[key]) {
      return normalizeProxyTargetUrl(image[key]);
    }
  }
  if (image.livePhoto && typeof image.livePhoto === "object") {
    const live = image.livePhoto;
    const candidates = [
      live.url,
      live.videoUrl,
      live.playUrl,
      live.urlDefault,
      live.urlNoWatermark,
    ];
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate) {
        return normalizeProxyTargetUrl(candidate);
      }
    }
  }
  if (image.video && typeof image.video === "object") {
    const candidates = [
      image.video.urlNoWatermark,
      image.video.urlDefault,
      image.video.url,
    ];
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate) {
        return normalizeProxyTargetUrl(candidate);
      }
    }
  }
  if (image.stream && typeof image.stream === "object") {
    const streamUrl = extractFromStream(image.stream);
    if (streamUrl) {
      return streamUrl;
    }
  }
  return null;
};

const getAuthorProfileUrl = (user: any) => {
  const candidate =
    user?.userId ??
    user?.userID ??
    user?.userid ??
    user?.id ??
    user?.user_id ??
    null;
  if (typeof candidate === "string" && candidate.trim()) {
    return `https://www.xiaohongshu.com/user/profile/${candidate.trim()}`;
  }
  if (typeof candidate === "number" && Number.isFinite(candidate)) {
    return `https://www.xiaohongshu.com/user/profile/${candidate}`;
  }
  return null;
};

const _INVALID_FILENAME_CHARS = /[<>:"/\\|?*\x00-\x1F]/g;

const sanitizeFilenameSegment = (value: unknown, fallback: string) => {
  const text = value === null || value === undefined ? "" : String(value);
  const cleaned = text
    .replace(_INVALID_FILENAME_CHARS, "_")
    .trim()
    .replace(/[. ]+$/g, "");
  return cleaned || fallback;
};

const truncateSegment = (value: string, maxLength: number) => {
  if (value.length <= maxLength) {
    return value;
  }
  return value.slice(0, maxLength).trim();
};

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
};

const inferImageExtension = (contentType: string | null, url: string) => {
  const normalized = (contentType ?? "").toLowerCase();
  if (normalized.includes("image/png")) {
    return "png";
  }
  if (normalized.includes("image/webp")) {
    return "webp";
  }
  if (normalized.includes("image/gif")) {
    return "gif";
  }
  if (normalized.includes("image/jpeg") || normalized.includes("image/jpg")) {
    return "jpg";
  }
  const lowerUrl = url.toLowerCase();
  const match = lowerUrl.match(/\.(jpg|jpeg|png|webp|gif)(\?|#|$)/);
  if (match) {
    return match[1] === "jpeg" ? "jpg" : match[1];
  }
  return "jpg";
};

const extractVideoUrl = (video: any): string => {
  if (!video) {
    return "";
  }

  const extractFromStream = (stream: any) => {
    if (!stream || typeof stream !== "object") {
      return "";
    }
    for (const key of ["h264", "h265", "av1", "h266"]) {
      const entries = stream[key];
      if (!Array.isArray(entries) || !entries.length) {
        continue;
      }
      const first = entries[0];
      if (!first || typeof first !== "object") {
        continue;
      }
      if (typeof first.masterUrl === "string" && first.masterUrl) {
        return normalizeProxyTargetUrl(first.masterUrl);
      }
      const backups = first.backupUrls;
      if (Array.isArray(backups) && typeof backups[0] === "string" && backups[0]) {
        return normalizeProxyTargetUrl(backups[0]);
      }
    }
    return "";
  };

  if (Array.isArray(video)) {
    for (const item of video) {
      if (!item || typeof item !== "object") {
        continue;
      }
      const direct =
        item.urlNoWatermark || item.urlDefault || item.url || "";
      if (typeof direct === "string" && direct) {
        return normalizeProxyTargetUrl(direct);
      }
      const streamUrl = extractFromStream(item?.media?.stream ?? item?.stream);
      if (streamUrl) {
        return streamUrl;
      }
    }
    return "";
  }

  if (typeof video === "object") {
    const direct =
      video.urlNoWatermark || video.urlDefault || video.url || "";
    if (typeof direct === "string" && direct) {
      return normalizeProxyTargetUrl(direct);
    }
    const streamUrl = extractFromStream(video?.media?.stream ?? video?.stream);
    if (streamUrl) {
      return streamUrl;
    }
  }
  return "";
};

const inferVideoExtension = (contentType: string | null, url: string) => {
  const normalized = (contentType ?? "").toLowerCase();
  if (normalized.includes("video/mp4")) {
    return "mp4";
  }
  if (normalized.includes("video/webm")) {
    return "webm";
  }
  if (normalized.includes("video/quicktime")) {
    return "mov";
  }
  if (
    normalized.includes("application/vnd.apple.mpegurl") ||
    normalized.includes("application/x-mpegurl")
  ) {
    return "m3u8";
  }
  const lowerUrl = url.toLowerCase();
  const match = lowerUrl.match(/\.(mp4|webm|mov|m3u8|ts)(\?|#|$)/);
  if (match) {
    return match[1];
  }
  return "mp4";
};

export default function App() {
  const [mode, setMode] = useState<Mode>("single");
  const [url, setUrl] = useState("");
  const [urlsText, setUrlsText] = useState("");
  const [timeoutInput, setTimeoutInput] = useState("15");
  const [userAgent, setUserAgent] = useState("");
  const [cookie, setCookie] = useState("");
  const [save, setSave] = useState(true);
  const [saveInitialState, setSaveInitialState] = useState(false);
  const [concurrency, setConcurrency] = useState(3);
  const [keepHistory, setKeepHistory] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ResultCard[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [outputs, setOutputs] = useState<OutputItem[]>([]);
  const [outputsLoading, setOutputsLoading] = useState(false);
  const [previewItems, setPreviewItems] = useState<PreviewItem[]>([]);
  const [previewIndex, setPreviewIndex] = useState(0);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [downloadingAll, setDownloadingAll] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) {
      return;
    }
    try {
      const parsed = JSON.parse(raw) as ResultCard[];
      setResults(parsed);
      setSelectedId(parsed[0]?.id ?? null);
    } catch {
      localStorage.removeItem(HISTORY_KEY);
    }
  }, []);

  useEffect(() => {
    if (!keepHistory) {
      return;
    }
    localStorage.setItem(HISTORY_KEY, JSON.stringify(results.slice(0, 15)));
  }, [keepHistory, results]);

  const selected = useMemo(
    () => results.find((item) => item.id === selectedId) ?? results[0],
    [results, selectedId]
  );

  const options: ParseOptions = useMemo(() => {
    const timeout =
      timeoutInput.trim().length > 0 ? Number(timeoutInput) : null;
    return {
      timeout: Number.isNaN(timeout) ? null : timeout,
      user_agent: userAgent.trim() || undefined,
      cookie: cookie.trim() || undefined,
      save,
      save_initial_state: saveInitialState,
    };
  }, [cookie, save, saveInitialState, timeoutInput, userAgent]);

  const addResults = (incoming: ResultCard[]) => {
    setResults((prev) => {
      const next = keepHistory ? [...incoming, ...prev] : incoming;
      return next.slice(0, 25);
    });
    setSelectedId(incoming[0]?.id ?? null);
  };

  const handleParse = async () => {
    setError(null);
    const timeoutValue = options.timeout;
    if (timeoutValue !== null && timeoutValue !== undefined) {
      if (timeoutValue < 1 || timeoutValue > 120) {
        setError("Timeout must be between 1 and 120 seconds.");
        return;
      }
    }

    if (mode === "single" && !url.trim()) {
      setError("Please provide a note URL.");
      return;
    }

    if (mode === "batch" && parseList(urlsText).length === 0) {
      setError("Please provide at least one URL in batch mode.");
      return;
    }

    setLoading(true);
    try {
      if (mode === "single") {
        const response = await parseSingle({ url: url.trim(), options });
        addResults([
          {
            id: buildId(),
            url: response.url,
            ok: true,
            options,
            response,
            createdAt: new Date().toISOString(),
          },
        ]);
      } else {
        const urls = parseList(urlsText);
        const batch = await parseBatch({
          urls,
          options,
          concurrency,
          dedupe: true,
        });
        const items = batch.items.map((item: BatchItem) => ({
          id: buildId(),
          url: item.url,
          ok: item.ok,
          options,
          response: item.result,
          error: item.error,
          createdAt: new Date().toISOString(),
        }));
        addResults(items);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setResults([]);
    setSelectedId(null);
    localStorage.removeItem(HISTORY_KEY);
  };

  const handleDownload = (note: Record<string, any>, filename: string) => {
    const blob = new Blob([stringifyJson(note)], { type: "application/json" });
    downloadBlob(blob, filename);
  };

  const openPreview = (items: PreviewItem[], index: number) => {
    if (!items.length) {
      return;
    }
    setPreviewItems(items);
    const clampedIndex = Math.max(0, Math.min(index, items.length - 1));
    setPreviewIndex(clampedIndex);
    setPreviewOpen(true);
  };

  const closePreview = () => {
    setPreviewOpen(false);
  };

  const previewCount = previewItems.length;
  const canNavigatePreview = previewCount > 1;

  const goPreviewPrev = useCallback(() => {
    if (!canNavigatePreview) {
      return;
    }
    setPreviewIndex(
      (current) => (current - 1 + previewCount) % previewCount
    );
  }, [canNavigatePreview, previewCount]);

  const goPreviewNext = useCallback(() => {
    if (!canNavigatePreview) {
      return;
    }
    setPreviewIndex((current) => (current + 1) % previewCount);
  }, [canNavigatePreview, previewCount]);

  const lastWheelAtRef = useRef(0);
  const wheelDeltaRef = useRef(0);

  const handlePreviewWheel = useCallback(
    (event: React.WheelEvent) => {
      if (!previewOpen || !canNavigatePreview) {
        return;
      }
      const current = previewItems[previewIndex];
      if (!current || current.type !== "image") {
        return;
      }
      event.preventDefault();
      event.stopPropagation();

      const now = Date.now();
      if (now - lastWheelAtRef.current > 350) {
        wheelDeltaRef.current = 0;
      }
      lastWheelAtRef.current = now;
      wheelDeltaRef.current += event.deltaY;

      if (Math.abs(wheelDeltaRef.current) < 60) {
        return;
      }

      if (wheelDeltaRef.current > 0) {
        goPreviewNext();
      } else {
        goPreviewPrev();
      }
      wheelDeltaRef.current = 0;
    },
    [
      canNavigatePreview,
      goPreviewNext,
      goPreviewPrev,
      previewIndex,
      previewItems,
      previewOpen,
    ]
  );

  useEffect(() => {
    if (!previewOpen) {
      return;
    }
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closePreview();
        return;
      }
      if (!canNavigatePreview) {
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        goPreviewPrev();
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        goPreviewNext();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = originalOverflow;
    };
  }, [canNavigatePreview, goPreviewNext, goPreviewPrev, previewOpen]);

  useEffect(() => {
    if (previewIndex < previewCount) {
      return;
    }
    setPreviewIndex(0);
  }, [previewCount, previewIndex]);

  const handleCopy = async (key: string, payload: unknown) => {
    try {
      await navigator.clipboard.writeText(stringifyJson(payload));
      setCopiedKey(key);
      window.setTimeout(() => {
        setCopiedKey((current) => (current === key ? null : current));
      }, 1500);
    } catch {
      setError("Copy failed. Please try again.");
    }
  };

  const downloadFile = async (url: string, filename: string) => {
    const normalizedUrl = normalizeMediaUrl(url);
    if (!normalizedUrl) {
      return;
    }
    try {
      const response = await fetch(normalizedUrl);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      const anchor = document.createElement("a");
      anchor.href = normalizedUrl;
      anchor.download = filename;
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
      anchor.click();
    }
  };

  const handleRefreshOutputs = async () => {
    setOutputsLoading(true);
    try {
      const response = await fetchOutputs(40);
      setOutputs(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load outputs.");
    } finally {
      setOutputsLoading(false);
    }
  };

  const note = selected?.response?.note ?? null;
  const user = note?.user ?? {};
  const authorProfileUrl = getAuthorProfileUrl(user);
  const imageList = Array.isArray(note?.imageList) ? note.imageList : [];
  const createTime = note?.CreateTime ?? note?.time ?? null;
  const interactInfo = note?.interactInfo ?? {};
  const tagNames = (Array.isArray(note?.tagList) ? note.tagList : [])
    .map((tag: any) => (typeof tag === "string" ? tag : tag?.name))
    .filter((name: any) => typeof name === "string" && name.trim())
    .map((name: string) => name.trim());
  const title = note?.title || "Untitled Note";
  const summary = note?.desc || note?.summary || "";
  const coverUrl = note ? getCoverUrl(note, imageList) : "";
  const primaryVideoUrl = extractVideoUrl(note?.video);
  const isVideoNote = note?.type === "video" || Boolean(primaryVideoUrl);

  const liveImages = imageList
    .map((image: any) => ({
      image,
      liveUrl: extractLiveUrl(image),
    }))
    .filter(
      (item) =>
        item.image?.isLivePhoto === true ||
        item.image?.livePhoto === true ||
        Boolean(item.liveUrl)
    );
  const liveGallery = liveImages.map((item) => ({
    ...item.image,
    liveUrl: item.liveUrl,
  }));
  const standardImages = imageList
    .filter(
      (image: any) =>
        !liveImages.some((liveItem) => liveItem.image === image) &&
        image?.urlNoWatermark !== coverUrl &&
        image?.urlDefault !== coverUrl
    )
    .filter((image: any) => Boolean(getImageUrl(image)));

  const livePreviewItems: PreviewItem[] = liveGallery
    .map((image: any, index: number) => ({
      type: image.liveUrl ? ("video" as const) : ("image" as const),
      url: image.liveUrl ? toMediaProxyUrl(image.liveUrl) : getImageUrl(image),
      poster: getImageUrl(image),
      title: `Live ${index + 1}`,
      loop: Boolean(image.liveUrl),
      muted: Boolean(image.liveUrl),
    }))
    .filter((item) => Boolean(item.url));

  const liveCoverImages = (() => {
    const seen = new Set<string>();
    const items: any[] = [];
    for (const image of liveGallery) {
      const url = getImageUrl(image);
      if (!url || url === coverUrl || seen.has(url)) {
        continue;
      }
      seen.add(url);
      items.push(image);
    }
    return items;
  })();

  const imageGallery: Array<{ kind: "cover" } | { kind: "image"; image: any }> =
    coverUrl
      ? [
          { kind: "cover" },
          ...liveCoverImages.map((image: any) => ({ kind: "image" as const, image })),
          ...standardImages.map((image: any) => ({ kind: "image" as const, image })),
        ]
      : [
          ...liveCoverImages.map((image: any) => ({ kind: "image" as const, image })),
          ...standardImages.map((image: any) => ({ kind: "image" as const, image })),
        ];

  const imagePreviewItems: PreviewItem[] = imageGallery
    .map((item: any, index: number) => {
      if (item.kind === "cover") {
        return { type: "image" as const, url: coverUrl, title: "Cover" };
      }
      const imageUrl = getImageUrl(item.image);
      return {
        type: "image" as const,
        url: imageUrl,
        title: `Image ${index + 1}`,
      };
    })
    .filter((item) => Boolean(item.url));

  const videoPreviewItems: PreviewItem[] = primaryVideoUrl
    ? [
        {
          type: "video" as const,
          url: toMediaProxyUrl(primaryVideoUrl),
          poster: coverUrl || undefined,
          title: "Video",
          loop: false,
          muted: false,
        },
      ]
    : [];

  const handleDownloadAllMedia = async () => {
    if (downloadingAll) {
      return;
    }

    const targets: Array<{
      kind: "image" | "video";
      url: string;
      filenameBase: string;
    }> = [];
    const seenUrls = new Set<string>();
    const pushTarget = (
      kind: "image" | "video",
      url: string,
      filenameBase: string
    ) => {
      const normalizedUrl = normalizeMediaUrl(url);
      if (!normalizedUrl || seenUrls.has(normalizedUrl)) {
        return;
      }
      seenUrls.add(normalizedUrl);
      targets.push({ kind, url: normalizedUrl, filenameBase });
    };

    if (coverUrl) {
      pushTarget("image", coverUrl, "cover");
    }

    if (!isVideoNote) {
      let imageIndex = 0;
      for (const image of standardImages) {
        const imageUrl = getImageUrl(image);
        if (!imageUrl || seenUrls.has(imageUrl)) {
          continue;
        }
        imageIndex += 1;
        pushTarget(
          "image",
          imageUrl,
          `image_${String(imageIndex).padStart(2, "0")}`
        );
      }
    }

    if (liveGallery.length > 0) {
      let liveIndex = 0;
      for (const image of liveGallery) {
        liveIndex += 1;
        const prefix = String(liveIndex).padStart(2, "0");
        const posterUrl = getImageUrl(image);
        if (posterUrl) {
          pushTarget("image", posterUrl, `live_${prefix}_poster`);
        }
        const liveUrl = image?.liveUrl;
        if (typeof liveUrl === "string" && liveUrl) {
          pushTarget("video", toMediaProxyUrl(liveUrl), `live_${prefix}`);
        }
      }
    }

    if (primaryVideoUrl) {
      pushTarget("video", toMediaProxyUrl(primaryVideoUrl), "video");
    }

    if (!targets.length) {
      return;
    }

    setDownloadingAll(true);
    try {
      const selectedOptions = selected?.options ?? options;
      const authorName = truncateSegment(
        sanitizeFilenameSegment(user.nickname, "unknown_author"),
        40
      );
      const titleName = truncateSegment(
        sanitizeFilenameSegment(note?.title, "untitled"),
        60
      );
      const noteId = sanitizeFilenameSegment(note?.noteId, "note");
      const zipBaseName = `${authorName}_${titleName}_${noteId}`;

      const entries: { name: string; data: Uint8Array }[] = [];
      const encoder = new TextEncoder();
      if (selectedOptions.save) {
        entries.push({
          name: "noteDetail.json",
          data: encoder.encode(stringifyJson(note)),
        });
      }
      if (selectedOptions.save_initial_state && selected?.response?.initial_state) {
        entries.push({
          name: "initial_state.json",
          data: encoder.encode(stringifyJson(selected.response.initial_state)),
        });
      }
      const usedNames = new Set<string>();
      for (const target of targets) {
        const response = await fetch(target.url);
        if (!response.ok) {
          throw new Error(`Failed to fetch media (${response.status}).`);
        }
        const contentType = response.headers.get("content-type");
        const ext =
          target.kind === "video"
            ? inferVideoExtension(contentType, target.url)
            : inferImageExtension(contentType, target.url);
        const base = `${target.filenameBase}.${ext}`;
        let filename = base;
        let suffix = 2;
        while (usedNames.has(filename)) {
          filename = `${target.filenameBase}_${suffix}.${ext}`;
          suffix += 1;
        }
        usedNames.add(filename);

        const buffer = await response.arrayBuffer();
        entries.push({ name: filename, data: new Uint8Array(buffer) });
      }

      const zipBytes = createZip(entries);
      const zipBuffer = (zipBytes.buffer as ArrayBuffer).slice(
        zipBytes.byteOffset,
        zipBytes.byteOffset + zipBytes.byteLength
      );
      downloadBlob(
        new Blob([zipBuffer], { type: "application/zip" }),
        `${zipBaseName}.zip`
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to download zip package."
      );
    } finally {
      setDownloadingAll(false);
    }
  };

  const activePreview = previewItems[previewIndex];

  const metrics = [
    {
      label: "Likes",
      value: interactInfo?.likedCount ?? note?.likedCount ?? note?.likeCount,
    },
    {
      label: "Collects",
      value:
        interactInfo?.collectedCount ??
        note?.collectedCount ??
        note?.collectCount,
    },
    { label: "Comments", value: interactInfo?.commentCount ?? note?.commentCount },
    { label: "Shares", value: interactInfo?.shareCount ?? note?.shareCount },
  ].filter((item) => item.value !== undefined && item.value !== null);

  return (
    <div className="page">
      <div className="backdrop">
        <div className="orb orb-one" />
        <div className="orb orb-two" />
        <div className="orb orb-three" />
      </div>

      <header className="hero">
        <div>
          <p className="eyebrow">XHS Note Parser Studio</p>
          <h1>Parse, enrich, and showcase Xiaohongshu notes in one flow.</h1>
          <p className="lead">
            Paste a note URL, tune headers, and instantly preview the structured
            detail JSON with no-watermark media links. Batch mode handles multiple
            notes in one run.
          </p>
          <div className="badge-row">
            <span className="badge">FastAPI backend</span>
            <span className="badge">Vite + React UI</span>
            <span className="badge">Output-ready JSON</span>
          </div>
        </div>
        <div className="hero-card">
          <h3>Quick tips</h3>
          <ul>
            <li>403? Add Cookie + User-Agent from your browser session.</li>
            <li>Enable “Save initial state” if you need raw page data.</li>
            <li>Batch mode accepts one URL per line.</li>
          </ul>
        </div>
      </header>

      <main className="layout">
        <section className="panel">
          <div className="panel-header">
            <h2>Parser Console</h2>
            <div className="mode-toggle">
              <button
                className={mode === "single" ? "active" : ""}
                type="button"
                onClick={() => setMode("single")}
              >
                Single
              </button>
              <button
                className={mode === "batch" ? "active" : ""}
                type="button"
                onClick={() => setMode("batch")}
              >
                Batch
              </button>
            </div>
          </div>

          {mode === "single" ? (
            <label className="field">
              <span>Note URL</span>
              <input
                placeholder="https://www.xiaohongshu.com/explore/..."
                value={url}
                onChange={(event) => setUrl(event.target.value)}
              />
            </label>
          ) : (
            <label className="field">
              <span>Note URLs (one per line)</span>
              <textarea
                placeholder="https://www.xiaohongshu.com/explore/...\nhttps://www.xiaohongshu.com/explore/..."
                value={urlsText}
                rows={6}
                onChange={(event) => setUrlsText(event.target.value)}
              />
            </label>
          )}

          <div className="grid two">
            <label className="field">
              <span>Timeout (seconds)</span>
              <input
                type="number"
                min={1}
                max={120}
                value={timeoutInput}
                onChange={(event) => setTimeoutInput(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Concurrency</span>
              <input
                type="number"
                min={1}
                max={10}
                value={concurrency}
                onChange={(event) => setConcurrency(Number(event.target.value))}
                disabled={mode !== "batch"}
              />
            </label>
          </div>

          <label className="field">
            <span>User-Agent</span>
            <input
              placeholder="Mozilla/5.0 ..."
              value={userAgent}
              onChange={(event) => setUserAgent(event.target.value)}
            />
          </label>

          <label className="field">
            <span>Cookie</span>
            <textarea
              rows={3}
              placeholder="Paste Cookie header if needed"
              value={cookie}
              onChange={(event) => setCookie(event.target.value)}
            />
          </label>

          <div className="toggle-row">
            <label className="toggle">
              <input
                type="checkbox"
                checked={save}
                onChange={(event) => setSave(event.target.checked)}
              />
              <span>Save noteDetail JSON</span>
            </label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={saveInitialState}
                onChange={(event) => setSaveInitialState(event.target.checked)}
              />
              <span>Save initial state JSON</span>
            </label>
          </div>

          <div className="actions">
            <button className="primary" type="button" onClick={handleParse}>
              {loading ? "Parsing..." : "Parse Now"}
            </button>
            <button type="button" onClick={handleClear}>
              Clear Results
            </button>
            <button
              type="button"
              onClick={() =>
                setUrl(EXAMPLE_URL)
              }
            >
              Load Example
            </button>
          </div>

          {error && <div className="error-banner">{error}</div>}

          <div className="panel-section">
            <div className="section-header">
              <h3>History</h3>
              <label className="toggle small">
                <input
                  type="checkbox"
                  checked={keepHistory}
                  onChange={(event) => setKeepHistory(event.target.checked)}
                />
                <span>Keep history</span>
              </label>
            </div>
            {results.length === 0 ? (
              <p className="muted">No runs yet.</p>
            ) : (
              <div className="history-list">
                {results.map((item) => (
                  <button
                    key={item.id}
                    className={
                      item.id === selected?.id ? "history-item active" : "history-item"
                    }
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                  >
                    <span className="history-title">
                      {item.response?.note?.title ?? item.url}
                    </span>
                    <span className={item.ok ? "status ok" : "status error"}>
                      {item.ok ? "OK" : "Error"}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="panel-section">
            <div className="section-header">
              <h3>Saved Outputs</h3>
              <button type="button" onClick={handleRefreshOutputs}>
                {outputsLoading ? "Refreshing..." : "Refresh"}
              </button>
            </div>
            {outputs.length === 0 ? (
              <p className="muted">No saved files found.</p>
            ) : (
              <div className="output-list">
                {outputs.map((item) => (
                  <div key={item.relative_path} className="output-item">
                    <div>
                      <strong>{item.kind}</strong>
                      <span>{item.relative_path}</span>
                    </div>
                    <span>{Math.round(item.size / 1024)} KB</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        <section className="viewer">
          {!selected && (
            <div className="empty">
              <h2>No result selected</h2>
              <p>Run a parse to see details here.</p>
            </div>
          )}

          {selected && !selected.ok && (
            <div className="result-card error">
              <h2>Parse failed</h2>
              <p className="muted">{selected.error}</p>
              <p className="muted">URL: {selected.url}</p>
            </div>
          )}

          {selected && selected.ok && note && (
            <div className="result-card">
              <div className="result-header">
                <div>
                  <h2 className="note-title">
                    <a
                      href={note.noteUrl || selected.url}
                      target="_blank"
                      rel="noreferrer"
                      title="Open note in new tab"
                    >
                      {title}
                    </a>
                  </h2>
                </div>
                <div className="result-actions">
                  <button
                    type="button"
                    onClick={() =>
                      handleDownload(
                        note,
                        `note_${note.noteId ?? "detail"}.json`
                      )
                    }
                  >
                    Download JSON
                  </button>
                </div>
              </div>

              <div className="note-info">
                <div className="cover-card">
                  {coverUrl ? (
                    <button
                      type="button"
                      className="cover-button"
                      onClick={() => openPreview(imagePreviewItems, 0)}
                    >
                      <img src={coverUrl} alt={title} />
                    </button>
                  ) : (
                    <div className="cover-placeholder">No cover</div>
                  )}
                  <div className="cover-meta">
                    <span>{user.nickname || "Unknown Author"}</span>
                    <span>{createTime ?? "-"}</span>
                  </div>
                </div>
                <div className="info-card">
                  <div className="meta-grid">
                    <div>
                      <span className="meta-label">Author</span>
                      <div className="author-row">
                        {user.avatar ? (
                          <img
                            className="avatar"
                            src={user.avatar}
                            alt={user.nickname ? `${user.nickname} avatar` : "avatar"}
                            loading="lazy"
                          />
                        ) : (
                          <div className="avatar avatar-placeholder" aria-hidden />
                        )}
                        <div className="author-text">
                          {authorProfileUrl ? (
                            <a
                              href={authorProfileUrl}
                              className="inline-link"
                              target="_blank"
                              rel="noreferrer"
                              title="Open author profile"
                            >
                              {user.nickname || "-"}
                            </a>
                          ) : (
                            <span>{user.nickname || "-"}</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div>
                      <span className="meta-label">User ID</span>
                      <span>{user.userId ?? "-"}</span>
                    </div>
                    <div>
                      <span className="meta-label">CreateTime</span>
                      <span>{createTime ?? "-"}</span>
                    </div>
                    <div>
                      <span className="meta-label">Last Update</span>
                      <span>{note.lastUpdateTime ?? "-"}</span>
                    </div>
                  </div>
                  {metrics.length > 0 && (
                    <div className="metric-row">
                      {metrics.map((metric) => (
                        <div key={metric.label} className="metric">
                          <span>{metric.label}</span>
                          <strong>{formatNumber(metric.value)}</strong>
                        </div>
                      ))}
                    </div>
                  )}
                  {tagNames.length > 0 && (
                    <div>
                      <span className="meta-label">Tags</span>
                      <div className="tag-list">
                        {tagNames.map((name, index) => (
                          <span key={`${name}-${index}`} className="tag-chip">
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {summary && <div className="note-content">{summary}</div>}

              {coverUrl && (
                <div>
                  <div className="section-header">
                    <h3>Cover</h3>
                  </div>
                  <button
                    type="button"
                    className="cover-large"
                    onClick={() => openPreview(imagePreviewItems, 0)}
                  >
                    <img src={coverUrl} alt={`${title} cover`} loading="lazy" />
                  </button>
                </div>
              )}

              {liveGallery.length > 0 && (
                <div>
                  <div className="section-header">
                    <h3>Live Gallery</h3>
                    <div className="section-actions">
                      <button
                        type="button"
                        onClick={handleDownloadAllMedia}
                        disabled={downloadingAll}
                      >
                        {downloadingAll ? "Packaging..." : "Download ZIP"}
                      </button>
                    </div>
                  </div>
                  <div className="media-grid">
                    {liveGallery.map((image: any, index: number) => {
                      const previewIndex = livePreviewItems.findIndex(
                        (item) =>
                          item.url ===
                          (image.liveUrl
                            ? toMediaProxyUrl(image.liveUrl)
                            : getImageUrl(image))
                      );
                      return (
                        <figure
                          key={image.traceId ?? `live-${index}`}
                          className="media-card"
                          onClick={() =>
                            openPreview(
                              livePreviewItems,
                              previewIndex === -1 ? 0 : previewIndex
                            )
                          }
                        >
                          <button
                            type="button"
                            className="media-preview"
                            onClick={() =>
                              openPreview(
                                livePreviewItems,
                                previewIndex === -1 ? 0 : previewIndex
                              )
                            }
                          >
                            {image.liveUrl ? (
                              <video
                                muted
                                loop
                                autoPlay
                                playsInline
                                preload="metadata"
                                poster={image.urlNoWatermark ?? image.urlDefault}
                                src={toMediaProxyUrl(image.liveUrl)}
                              />
                            ) : (
                              <img
                                src={image.urlNoWatermark ?? image.urlDefault}
                                alt={`${title} live`}
                                loading="lazy"
                              />
                            )}
                          </button>
                        </figure>
                      );
                    })}
                  </div>
                </div>
              )}

              {!isVideoNote && imagePreviewItems.length > 0 && (
                <div>
                  <div className="section-header">
                    <h3>Images</h3>
                    <div className="section-actions">
                      <button
                        type="button"
                        onClick={handleDownloadAllMedia}
                        disabled={downloadingAll}
                      >
                        {downloadingAll ? "Packaging..." : "Download ZIP"}
                      </button>
                    </div>
                  </div>
                  <div className="media-grid">
                    {imageGallery.map((item: any, index: number) => {
                      const url =
                        item.kind === "cover" ? coverUrl : getImageUrl(item.image);
                      const filenameBase = item.kind === "cover" ? "cover" : index + 1;
                      const filename = `note_${note?.noteId ?? "detail"}_image_${filenameBase}.jpg`;
                      return (
                        <figure
                          key={
                            item.kind === "cover"
                              ? "cover"
                              : item.image?.traceId ?? index
                          }
                          className="media-card"
                          onClick={() => openPreview(imagePreviewItems, index)}
                        >
                          <button
                            type="button"
                            className="media-preview"
                            onClick={() => openPreview(imagePreviewItems, index)}
                          >
                            <img src={url} alt={title} loading="lazy" />
                          </button>
                          <div className="media-overlay">
                            <button
                              type="button"
                              onClick={(event) => {
                                event.stopPropagation();
                                downloadFile(url, filename);
                              }}
                            >
                              Download
                            </button>
                          </div>
                        </figure>
                      );
                    })}
                  </div>
                </div>
              )}

              {isVideoNote && videoPreviewItems.length > 0 && (
                <div>
                  <div className="section-header">
                    <h3>Video</h3>
                    <div className="section-actions">
                      <button
                        type="button"
                        onClick={handleDownloadAllMedia}
                        disabled={downloadingAll}
                      >
                        {downloadingAll ? "Packaging..." : "Download ZIP"}
                      </button>
                    </div>
                  </div>
                  <div className="media-grid">
                    <figure
                      key="video"
                      className="media-card"
                      onClick={() => openPreview(videoPreviewItems, 0)}
                    >
                      <button
                        type="button"
                        className="media-preview"
                        onClick={() => openPreview(videoPreviewItems, 0)}
                      >
                        {coverUrl ? (
                          <img
                            src={coverUrl}
                            alt={`${title} video cover`}
                            loading="lazy"
                          />
                          ) : (
                            <video
                              muted
                              loop
                              autoPlay
                              playsInline
                              preload="metadata"
                              src={toMediaProxyUrl(primaryVideoUrl)}
                            />
                          )}
                      </button>
                      <div className="media-overlay">
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            const ext = inferVideoExtension(null, primaryVideoUrl);
                            downloadFile(
                              toMediaProxyUrl(primaryVideoUrl),
                              `note_${note?.noteId ?? "detail"}_video.${ext}`
                            );
                          }}
                        >
                          Download
                        </button>
                      </div>
                    </figure>
                  </div>
                </div>
              )}

              {selected.response?.saved && (
                <div className="saved-block">
                  <h3>Saved Paths</h3>
                  {selected.response.saved.note_detail && (
                    <p>
                      Note detail: <span>{selected.response.saved.note_detail}</span>
                    </p>
                  )}
                  {selected.response.saved.initial_state && (
                    <p>
                      Initial state:{" "}
                      <span>{selected.response.saved.initial_state}</span>
                    </p>
                  )}
                </div>
              )}

              {selected.response?.initial_state && (
                <details className="json-block">
                  <summary>
                    <span>Initial State JSON</span>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        handleCopy("initial", selected.response?.initial_state);
                      }}
                    >
                      {copiedKey === "initial" ? "Copied" : "Copy"}
                    </button>
                  </summary>
                  <pre>{stringifyJson(selected.response.initial_state)}</pre>
                </details>
              )}

              <details className="json-block">
                <summary>
                  <span>noteDetail JSON</span>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      handleCopy("noteDetail", note);
                    }}
                  >
                    {copiedKey === "noteDetail" ? "Copied" : "Copy"}
                  </button>
                </summary>
                <pre>{stringifyJson(note)}</pre>
              </details>
            </div>
          )}
        </section>
      </main>

              {previewOpen && activePreview && (
                <div
                  className="preview-overlay"
                  onClick={closePreview}
                  onWheel={handlePreviewWheel}
                >
                  <div
                    className="preview-viewport"
                    onClick={(event) => event.stopPropagation()}
                  >
                    {activePreview.type === "image" ? (
                      <img
                        className="preview-media"
                        src={activePreview.url}
                        alt={activePreview.title}
                        draggable={false}
                      />
                    ) : (
                      <video
                        className="preview-media"
                        controls
                        playsInline
                        autoPlay
                        muted={Boolean(activePreview.muted)}
                        loop={Boolean(activePreview.loop)}
                        poster={activePreview.poster}
                        src={activePreview.url}
                      />
                    )}
                  </div>
                  {canNavigatePreview && (
                    <>
                      <button
                        type="button"
                        className="preview-arrow preview-arrow-left"
                        onClick={(event) => {
                          event.stopPropagation();
                          goPreviewPrev();
                        }}
                        aria-label="Previous"
                        title="Previous (←)"
                      >
                        ‹
                      </button>
                      <button
                        type="button"
                        className="preview-arrow preview-arrow-right"
                        onClick={(event) => {
                          event.stopPropagation();
                          goPreviewNext();
                        }}
                        aria-label="Next"
                        title="Next (→)"
                      >
                        ›
                      </button>
                    </>
                  )}
                </div>
              )}
    </div>
  );
}
