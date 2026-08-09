import type {
  AwardGenerated,
  Counts,
  SeriesGenerated,
  StaffGenerated,
  StudioGenerated,
  ThemeGenerated,
  VoiceActorGenerated,
  WorkGenerated,
} from "../types";

function dataUrl(relativePath: string): string {
  return `${import.meta.env.BASE_URL}data/generated/${relativePath}`;
}

const cache = new Map<string, Promise<unknown>>();

function fetchJson<T>(file: string): Promise<T> {
  let pending = cache.get(file) as Promise<T> | undefined;
  if (!pending) {
    pending = fetch(dataUrl(file)).then((res) => {
      if (!res.ok) throw new Error(`Failed to load ${file}: ${res.status}`);
      return res.json() as Promise<T>;
    });
    cache.set(file, pending);
  }
  return pending;
}

export const getWorks = () => fetchJson<WorkGenerated[]>("works.json");
export const getStaff = () => fetchJson<StaffGenerated[]>("staff.json");
export const getStudios = () => fetchJson<StudioGenerated[]>("studios.json");
export const getVoiceActors = () => fetchJson<VoiceActorGenerated[]>("voiceActors.json");
export const getSeries = () => fetchJson<SeriesGenerated[]>("series.json");
export const getThemes = () => fetchJson<ThemeGenerated[]>("themes.json");
export const getAwards = () => fetchJson<AwardGenerated[]>("awards.json");
export const getCounts = () => fetchJson<Counts>("counts.json");

export async function getWork(workId: string): Promise<WorkGenerated | undefined> {
  const works = await getWorks();
  return works.find((w) => w.id === workId);
}

export async function getStaffMember(staffId: string): Promise<StaffGenerated | undefined> {
  const staff = await getStaff();
  return staff.find((s) => s.id === staffId);
}

export async function getStudio(studioId: string): Promise<StudioGenerated | undefined> {
  const studios = await getStudios();
  return studios.find((s) => s.id === studioId);
}

export async function getVoiceActor(voiceActorId: string): Promise<VoiceActorGenerated | undefined> {
  const voiceActors = await getVoiceActors();
  return voiceActors.find((v) => v.id === voiceActorId);
}

export async function getSeriesItem(seriesId: string): Promise<SeriesGenerated | undefined> {
  const series = await getSeries();
  return series.find((x) => x.id === seriesId);
}

export async function getTheme(themeId: string): Promise<ThemeGenerated | undefined> {
  const themes = await getThemes();
  return themes.find((t) => t.id === themeId);
}

export async function getAward(awardId: string): Promise<AwardGenerated | undefined> {
  const awards = await getAwards();
  return awards.find((a) => a.id === awardId);
}
