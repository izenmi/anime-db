import { BrowserRouter, Route, Routes } from "react-router-dom";
import { TopNav } from "./ui/common/TopNav";
import { ScrollToTop } from "./ui/common/ScrollToTop";
import { HomePage } from "./ui/home/HomePage";
import { WorkListPage } from "./ui/works/WorkListPage";
import { WorkDetailPage } from "./ui/works/WorkDetailPage";
import { ThemeListPage } from "./ui/themes/ThemeListPage";
import { ThemeDetailPage } from "./ui/themes/ThemeDetailPage";
import { StaffListPage } from "./ui/staff/StaffListPage";
import { StaffDetailPage } from "./ui/staff/StaffDetailPage";
import { StudioListPage } from "./ui/studios/StudioListPage";
import { StudioDetailPage } from "./ui/studios/StudioDetailPage";
import { VoiceActorListPage } from "./ui/cast/VoiceActorListPage";
import { VoiceActorDetailPage } from "./ui/cast/VoiceActorDetailPage";
import { AwardListPage } from "./ui/awards/AwardListPage";
import { AwardDetailPage } from "./ui/awards/AwardDetailPage";
import { AboutPage } from "./ui/about/AboutPage";
import { NotFoundPage } from "./ui/common/NotFoundPage";
import { AffiliateNotice } from "./ui/common/AffiliateNotice";

export function App() {
  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      <ScrollToTop />
      <TopNav />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/works" element={<WorkListPage />} />
        <Route path="/works/:id" element={<WorkDetailPage />} />
        <Route path="/themes" element={<ThemeListPage />} />
        <Route path="/themes/:id" element={<ThemeDetailPage />} />
        <Route path="/staff" element={<StaffListPage />} />
        <Route path="/staff/:id" element={<StaffDetailPage />} />
        <Route path="/studios" element={<StudioListPage />} />
        <Route path="/studios/:id" element={<StudioDetailPage />} />
        <Route path="/cast" element={<VoiceActorListPage />} />
        <Route path="/cast/:id" element={<VoiceActorDetailPage />} />
        <Route path="/awards" element={<AwardListPage />} />
        <Route path="/awards/:id" element={<AwardDetailPage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <AffiliateNotice />
    </BrowserRouter>
  );
}
