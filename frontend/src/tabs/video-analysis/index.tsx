import { useCallback, useEffect, useMemo, useState } from "react";
import { videoApi } from "./api";
import ProfilePanel from "./components/ProfilePanel";
import TraitBoard from "./components/TraitBoard";
import UploadForm from "./components/UploadForm";
import ClipList from "./components/ClipList";
import AnalysisDetail from "./components/AnalysisDetail";
import type {
  Clip,
  ClipDetail,
  ModelHealth,
  Profile,
  ProfileImage,
  ProfileIn,
  Side,
  Trait,
  TraitIn,
} from "./types";

export default function VideoAnalysis() {
  const [health, setHealth] = useState<ModelHealth | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [images, setImages] = useState<ProfileImage[]>([]);
  const [traits, setTraits] = useState<Trait[]>([]);
  const [clips, setClips] = useState<Clip[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<ClipDetail | null>(null);

  const [uploading, setUploading] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [identifying, setIdentifying] = useState(false);
  const [cropping, setCropping] = useState(false);
  // Bumped whenever a clip's preview image changes at its (stable) URL, so the
  // browser re-fetches it instead of showing a cached thumbnail.
  const [previewBust, setPreviewBust] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  const reloadClips = useCallback(async () => setClips(await videoApi.listClips()), []);
  const reloadTraits = useCallback(async () => setTraits(await videoApi.listTraits()), []);
  const reloadImages = useCallback(async () => setImages(await videoApi.listProfileImages()), []);
  const reloadDetail = useCallback(async (id: number) => {
    setDetail(await videoApi.getClip(id));
  }, []);

  // Initial load.
  useEffect(() => {
    (async () => {
      try {
        const [h, p, t, c, im] = await Promise.all([
          videoApi.health(),
          videoApi.getProfile(),
          videoApi.listTraits(),
          videoApi.listClips(),
          videoApi.listProfileImages(),
        ]);
        setHealth(h);
        setProfile(p);
        setTraits(t);
        setClips(c);
        setImages(im);
      } catch (e) {
        fail(e);
      }
    })();
  }, []);

  // Load detail when selection changes.
  useEffect(() => {
    if (selectedId == null) {
      setDetail(null);
      return;
    }
    void reloadDetail(selectedId).catch(fail);
  }, [selectedId, reloadDetail]);

  // Poll while any clip is still being analysed.
  const anyProcessing = useMemo(
    () =>
      clips.some(
        (c) =>
          c.status === "processing" ||
          c.status === "pending" ||
          c.status === "analyzing"
      ),
    [clips]
  );
  useEffect(() => {
    if (!anyProcessing) return;
    const timer = setInterval(() => {
      void reloadClips().catch(() => {});
      void reloadTraits().catch(() => {});
      void reloadImages().catch(() => {});
      if (selectedId != null) void reloadDetail(selectedId).catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [anyProcessing, selectedId, reloadClips, reloadTraits, reloadImages, reloadDetail]);

  const handleBrowse = async (kind: "video" | "image"): Promise<string> => {
    try {
      return (await videoApi.browse(kind)).path;
    } catch (e) {
      fail(e);
      return "";
    }
  };

  const handleAddImage = async () => {
    const path = await handleBrowse("image");
    if (!path) return;
    try {
      await videoApi.addProfileImage(path);
      await reloadImages();
    } catch (e) {
      fail(e);
    }
  };

  const handleDeleteImage = async (id: number) => {
    try {
      await videoApi.deleteProfileImage(id);
      await reloadImages();
    } catch (e) {
      fail(e);
    }
  };

  const handleIdentify = async (sideValue: Side, appearance: string) => {
    if (selectedId == null) return;
    setIdentifying(true);
    try {
      await videoApi.identify(selectedId, sideValue, appearance);
      await reloadClips();
      await reloadDetail(selectedId);
    } catch (e) {
      fail(e);
    } finally {
      setIdentifying(false);
    }
  };

  const handleCropReference = async (box: {
    x: number;
    y: number;
    w: number;
    h: number;
  }): Promise<boolean> => {
    if (selectedId == null) return false;
    setCropping(true);
    try {
      await videoApi.cropReference(selectedId, box);
      await Promise.all([reloadImages(), reloadDetail(selectedId)]);
      setPreviewBust((v) => v + 1); // preview file changed at the same URL
      return true;
    } catch (e) {
      fail(e);
      return false;
    } finally {
      setCropping(false);
    }
  };

  const handleConfirm = async () => {
    if (selectedId == null) return;
    setIdentifying(true);
    try {
      await videoApi.confirm(selectedId);
      await reloadClips();
      await reloadDetail(selectedId);
    } catch (e) {
      fail(e);
    } finally {
      setIdentifying(false);
    }
  };

  // ---- handlers ----
  const handleCreate = async (form: Parameters<typeof videoApi.createClip>[0]) => {
    setError(null);
    setUploading(true);
    try {
      const clip = await videoApi.createClip(form);
      await reloadClips();
      setSelectedId(clip.id);
    } catch (e) {
      fail(e);
    } finally {
      setUploading(false);
    }
  };

  const handleSaveProfile = async (payload: ProfileIn) => {
    try {
      setProfile(await videoApi.updateProfile(payload));
    } catch (e) {
      fail(e);
    }
  };

  const handleRegenerate = async () => {
    setError(null);
    setRegenerating(true);
    try {
      setProfile(await videoApi.regenerateSummary());
    } catch (e) {
      fail(e);
    } finally {
      setRegenerating(false);
    }
  };

  const handleAddTrait = async (payload: TraitIn) => {
    try {
      await videoApi.createTrait(payload);
      await reloadTraits();
    } catch (e) {
      fail(e);
    }
  };

  const handleDeleteTrait = async (id: number) => {
    try {
      await videoApi.deleteTrait(id);
      await reloadTraits();
    } catch (e) {
      fail(e);
    }
  };

  const handleReanalyze = async () => {
    if (selectedId == null) return;
    setReanalyzing(true);
    try {
      await videoApi.reanalyze(selectedId, detail?.model || undefined);
      await reloadClips();
      await reloadDetail(selectedId);
    } catch (e) {
      fail(e);
    } finally {
      setReanalyzing(false);
    }
  };

  const handleDeleteClip = async () => {
    if (selectedId == null) return;
    if (!window.confirm("Xóa clip này (cả file và phân tích)?")) return;
    try {
      await videoApi.deleteClip(selectedId);
      setSelectedId(null);
      await Promise.all([reloadClips(), reloadTraits()]);
    } catch (e) {
      fail(e);
    }
  };

  return (
    <div className="va-tab">
      {error && <div className="pb-error">{error}</div>}

      <div className="va-layout">
        {/* Left: the player profile */}
        <div className="va-col">
          {profile && (
            <ProfilePanel
              profile={profile}
              images={images}
              onSave={handleSaveProfile}
              onRegenerate={handleRegenerate}
              onAddImage={handleAddImage}
              onDeleteImage={handleDeleteImage}
              regenerating={regenerating}
              canRegenerate={traits.length > 0}
            />
          )}
          <TraitBoard traits={traits} onAdd={handleAddTrait} onDelete={handleDeleteTrait} />
        </div>

        {/* Right: clips + analysis */}
        <div className="va-col">
          <UploadForm
            health={health}
            uploading={uploading}
            onBrowse={() => handleBrowse("video")}
            onCreate={handleCreate}
          />
          <section className="va-card">
            <div className="va-card-head">
              <h3>🎬 Các clip</h3>
              {anyProcessing && <span className="va-muted">đang cập nhật…</span>}
            </div>
            <ClipList clips={clips} selectedId={selectedId} onSelect={setSelectedId} />
          </section>
          {detail && (
            <AnalysisDetail
              detail={detail}
              videoUrl={videoApi.videoUrl(detail.id)}
              previewUrl={`${videoApi.previewUrl(detail.id)}?v=${previewBust}`}
              frameUrl={videoApi.frameUrl(detail.id)}
              reanalyzing={reanalyzing}
              identifying={identifying}
              cropping={cropping}
              onReanalyze={handleReanalyze}
              onIdentify={handleIdentify}
              onConfirm={handleConfirm}
              onCropReference={handleCropReference}
              onDelete={handleDeleteClip}
            />
          )}
        </div>
      </div>
    </div>
  );
}
