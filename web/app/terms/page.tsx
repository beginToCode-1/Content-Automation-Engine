import type { Metadata } from "next";
import PageHeader from "@/components/PageHeader";

export const metadata: Metadata = {
  title: "Terms of Service - Content Engine",
};

export default function TermsPage() {
  return (
    <>
      <PageHeader breadcrumb="Terms" title="Terms of Service" action={null} />
      <div className="doc-page">
        <p className="doc-updated">Last updated: September 4, 2026</p>

        <p>
          Content Engine is self-hosted software that automates finding source video content, producing a
          short-form vertical clip from it, and publishing that clip to connected social media accounts. These
          terms apply to whoever operates and uses a running instance of this application.
        </p>

        <h2>Provided As-Is</h2>
        <p>
          This software is provided without warranty of any kind. The developer is not responsible for lost data,
          failed uploads, account restrictions, or any other outcome resulting from running this application.
        </p>

        <h2>Responsibility for Published Content</h2>
        <p>The operator is solely responsible for the content this application generates and publishes. This includes:</p>
        <ul>
          <li>Ensuring the operator has the right to use any source video content downloaded and re-edited by this application</li>
          <li>Complying with the Terms of Service of every platform the application connects to, including YouTube, Instagram, and TikTok</li>
          <li>Reviewing generated titles, descriptions, and clips before making them public</li>
        </ul>

        <h2>Third-Party Platform Risk</h2>
        <p>
          Re-using downloaded video content can result in copyright claims, content takedowns, or account
          enforcement action from the platform where the content is downloaded from or published to. The developer
          has no control over and no responsibility for actions taken by YouTube, Instagram, TikTok, or any other
          third-party platform against an operator&apos;s account.
        </p>

        <h2>No Guarantee of Availability</h2>
        <p>
          Because this application runs on infrastructure the operator controls, there is no uptime guarantee.
          Third-party API changes, quota limits, or credential expiration can affect functionality at any time.
        </p>

        <h2>Changes to These Terms</h2>
        <p>
          These terms may be updated as the application&apos;s functionality changes. Continued use of the
          application after an update constitutes acceptance of the revised terms.
        </p>
      </div>
    </>
  );
}
