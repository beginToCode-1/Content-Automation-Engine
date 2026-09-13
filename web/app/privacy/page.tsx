import type { Metadata } from "next";
import PageHeader from "@/components/PageHeader";

export const metadata: Metadata = {
  title: "Privacy Policy - Content Engine",
};

export default function PrivacyPage() {
  return (
    <>
      <PageHeader breadcrumb="Privacy" title="Privacy Policy" action={null} />
      <div className="doc-page">
        <p className="doc-updated">Last updated: September 13, 2026</p>

        <p>
          Content Engine is operated by whoever deployed this instance - it is not a hosted service operated by a
          separate company, and there is no remote server collecting your data on the developer&apos;s behalf beyond
          the operator&apos;s own deployment described below. This policy describes how the application handles data
          and which third-party services it connects to on your behalf.
        </p>

        <h2>Data This Application Stores</h2>
        <p>
          Accounts, run history, schedules, connected-platform tokens, and similar structured data are stored in a
          Postgres database the operator controls (hosted with a database provider such as Supabase) - not
          transmitted to any server operated by the developer of this software. Downloaded video files and rendered
          clips are stored as local files on the machine running the backend.
        </p>
        <ul>
          <li>Your account (email, password hash, role) and login sessions</li>
          <li>Topics you enter to start a run</li>
          <li>Metadata about source videos found through YouTube search (title, description, video ID)</li>
          <li>Downloaded video files and the rendered clips produced from them (local files)</li>
          <li>Transcripts fetched for source videos</li>
          <li>Titles, descriptions, and hashtags generated for each clip</li>
          <li>Run history and scheduled topics you configure</li>
          <li>OAuth access tokens and API credentials for the platforms you connect (Google, Instagram, TikTok),
            encrypted at rest</li>
        </ul>

        <h2>Third-Party Services</h2>
        <p>
          To do its job, this application makes requests to the following third-party services using credentials
          the operator supplies. Each service&apos;s own privacy policy governs how it handles data sent to it:
        </p>
        <ul>
          <li>Database provider (e.g. Supabase) - stores the structured data listed above on the operator&apos;s
            behalf</li>
          <li>YouTube Data API (Google) - used to search for and download source video content</li>
          <li>Google Gemini API - used to generate clip titles, descriptions, and hashtags</li>
          <li>Instagram Graph API (Meta) - used to publish content to a connected Instagram account</li>
          <li>TikTok Content Posting API - used to publish content to a connected TikTok account</li>
        </ul>

        <h2>No Analytics or Tracking</h2>
        <p>
          This application does not include any analytics, telemetry, or third-party tracking scripts. It does not
          use cookies beyond what is required to operate the local web dashboard in your browser during a session.
        </p>

        <h2>Data Control</h2>
        <p>
          The operator has full control over this data at all times. Deleting the records in the operator&apos;s
          Postgres database and the application&apos;s local working directory removes all stored accounts, run
          history, credentials, and generated media.
        </p>

        <h2>Contact</h2>
        <p>
          This application has no separate operating company. Questions about a specific deployment should be
          directed to whoever operates that instance.
        </p>
      </div>
    </>
  );
}
