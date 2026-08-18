import './PrivacyPage.css'

/**
 * PrivacyPage renders Venera's Privacy Policy (see /PRIVACY.md at the
 * repository root, which is the canonical source for this content).
 * It has no data dependencies of its own -- it's a static informational
 * page linked from the site footer.
 */
export default function PrivacyPage() {
    return (
        <div className="policy-card">
            <div className="policy-header">
                <span className="policy-icon" aria-hidden="true">
                    🔒
                </span>
                <div>
                    <h2 className="policy-title">Privacy Policy</h2>
                    <p className="policy-effective-date">
                        Effective Date: August 18, 2026
                    </p>
                </div>
            </div>

            <div className="policy-body">
                <p>
                    Venera (&ldquo;Venera,&rdquo; &ldquo;the Service,&rdquo;
                    &ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;) is
                    a web application for planning stargazing and
                    astrophotography sessions using astronomical, weather, and
                    location data.
                </p>
                <p>
                    This Privacy Policy explains what information Venera
                    processes, why it is processed, how long it is retained, and
                    the rights available to users under applicable privacy laws,
                    including the European Union General Data Protection
                    Regulation (&ldquo;GDPR&rdquo;) and the California Consumer
                    Privacy Act (&ldquo;CCPA&rdquo;), as amended by the
                    California Privacy Rights Act (&ldquo;CPRA&rdquo;).
                </p>

                <section className="policy-section">
                    <h3>1. Data Controller</h3>
                    <p>Venera is operated by:</p>
                    <p>
                        <strong>Ben O&rsquo;Neill</strong>
                        <br />
                        Email: <a href="mailto:ben@oneill.sh">ben@oneill.sh</a>
                    </p>
                    <p>
                        For purposes of the GDPR, Ben O&rsquo;Neill is the data
                        controller for personal data processed by Venera.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>2. Information Venera Processes</h3>
                    <p>
                        Venera is designed to collect and retain as little
                        personal information as reasonably possible.
                    </p>

                    <h4>Location Information</h4>
                    <p>
                        Some Venera features require a location in order to
                        calculate astronomical visibility, provide weather
                        information, or recommend observing conditions.
                    </p>
                    <p>
                        You may provide a location through information such as:
                    </p>
                    <ul>
                        <li>a municipality or place name; or</li>
                        <li>latitude and longitude coordinates</li>
                    </ul>
                    <p>
                        <strong>
                            Venera does not retain or log the location
                            information you provide for these purposes.
                        </strong>
                    </p>
                    <p>
                        Location information is processed only as necessary to
                        perform the requested calculation or provide the
                        requested information. It is not associated with a user
                        account or maintained as a history of locations you have
                        searched.
                    </p>
                    <p>
                        If device location services are used, your browser or
                        operating system may separately request your permission
                        before providing location information to Venera.
                    </p>

                    <h4>IP Addresses</h4>
                    <p>
                        When you access Venera, the server or hosting
                        infrastructure may record your{' '}
                        <strong>IP address</strong> in server access or security
                        logs.
                    </p>
                    <p>
                        IP addresses are used by Venera only for purposes such
                        as:
                    </p>
                    <ul>
                        <li>operating and securing the Service;</li>
                        <li>
                            detecting abuse, attacks, or unauthorized activity;
                        </li>
                        <li>diagnosing technical problems; and</li>
                        <li>maintaining server reliability.</li>
                    </ul>
                    <p>
                        Venera does not use IP addresses to create user
                        profiles, track users across websites, serve targeted
                        advertising, or intentionally determine or retain
                        users&rsquo; physical locations.
                    </p>
                    <p>
                        Server access logs containing IP addresses are retained
                        for <strong>no more than 30 days</strong>, except where
                        a particular record must be retained longer to
                        investigate a security incident, abuse, or legal
                        obligation.
                    </p>

                    <h4>Communications</h4>
                    <p>
                        If you voluntarily contact Venera by email or another
                        provided communication method, we may receive your email
                        address and any information you include in your message.
                    </p>
                    <p>
                        That information is used only to respond to the
                        communication, address a reported problem, or otherwise
                        handle the reason you contacted us.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>3. No User Accounts</h3>
                    <p>
                        Venera does not currently require user accounts and does
                        not routinely collect names, passwords, account
                        profiles, or other account information.
                    </p>
                    <p>
                        If account functionality is introduced in the future,
                        this Privacy Policy will be updated before or when such
                        information begins to be collected.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>4. Cookies and Tracking</h3>
                    <p>
                        Venera does not use advertising cookies or cross-site
                        tracking technologies.
                    </p>
                    <p>
                        Venera does not use personal information for behavioral
                        or targeted advertising.
                    </p>
                    <p>
                        If analytics, advertising, or other tracking
                        technologies are introduced in the future, this Privacy
                        Policy and, where required, the Service&rsquo;s consent
                        mechanisms will be updated before those technologies are
                        enabled.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>5. How Information Is Used</h3>
                    <p>
                        Personal data processed by Venera is used only as
                        reasonably necessary to:
                    </p>
                    <ul>
                        <li>provide requested Venera functionality;</li>
                        <li>
                            calculate astronomical and observing information;
                        </li>
                        <li>obtain relevant weather information;</li>
                        <li>operate and maintain the Service;</li>
                        <li>
                            protect Venera and its infrastructure against abuse
                            or security threats;
                        </li>
                        <li>diagnose errors and technical problems;</li>
                        <li>comply with applicable legal obligations; and</li>
                        <li>respond to communications from users.</li>
                    </ul>
                    <p>
                        Venera does not use personal data for automated
                        decisions that produce legal or similarly significant
                        effects.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>6. Third-Party Services and Data Sources</h3>
                    <p>
                        Venera uses external services and datasets to provide
                        its functionality.
                    </p>

                    <h4>Open-Meteo</h4>
                    <p>Venera uses Open-Meteo to obtain weather information.</p>
                    <p>
                        When weather information is requested for a location,
                        geographic coordinates associated with the requested
                        location may be transmitted to Open-Meteo as part of the
                        weather-data request.
                    </p>
                    <p>
                        Venera does not intentionally transmit your identity or
                        your Venera access-log IP address to Open-Meteo as part
                        of that request.
                    </p>
                    <p>
                        Open-Meteo operates independently and may process
                        requests according to its own privacy practices.
                    </p>

                    <h4>GeoNames</h4>
                    <p>
                        Venera uses GeoNames geographic data for municipality
                        and location lookup.
                    </p>
                    <p>
                        Venera uses a locally imported copy of the relevant
                        GeoNames dataset. User searches therefore do not need to
                        be sent to GeoNames merely to perform municipality
                        lookup.
                    </p>

                    <h4>NASA JPL Ephemerides</h4>
                    <p>
                        Venera uses astronomical ephemeris data originating from
                        NASA&rsquo;s Jet Propulsion Laboratory for celestial
                        calculations.
                    </p>
                    <p>
                        Venera uses a locally imported copy of the relevant JPL
                        dataset. No user information is sent to NASA.
                    </p>

                    <h4>Hosting and Infrastructure Providers</h4>
                    <p>
                        The hosting, networking, or infrastructure providers
                        used to operate Venera may necessarily process technical
                        connection information, including IP addresses, in order
                        to deliver requests to the Service and maintain their
                        infrastructure.
                    </p>
                    <p>
                        Such providers may process information under their own
                        legal obligations and contractual terms.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>7. Legal Bases for Processing Under the GDPR</h3>
                    <p>
                        Where the GDPR applies, Venera processes personal data
                        under one or more of the following legal bases:
                    </p>

                    <h4>Legitimate Interests</h4>
                    <p>
                        IP addresses and related security information may be
                        processed where necessary for Venera&rsquo;s legitimate
                        interests in operating, securing, maintaining, and
                        protecting the Service.
                    </p>
                    <p>
                        These interests are balanced against the privacy rights
                        and interests of users, and Venera limits the
                        information retained for these purposes.
                    </p>

                    <h4>Providing Requested Functionality</h4>
                    <p>
                        Location information supplied by a user is processed
                        only as necessary to provide the astronomical, weather,
                        or observing functionality requested by that user.
                    </p>
                    <p>
                        Where applicable law requires consent for access to
                        device location information, Venera will rely on the
                        user&rsquo;s affirmative permission before obtaining
                        that information.
                    </p>

                    <h4>Legal Obligations</h4>
                    <p>
                        Information may be processed or retained when reasonably
                        necessary to comply with an applicable legal obligation.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>8. Data Retention</h3>
                    <p>Venera follows a data-minimization approach.</p>
                    <ul>
                        <li>
                            <strong>Location information:</strong> processed
                            transiently and not retained in Venera logs or
                            databases.
                        </li>
                        <li>
                            <strong>IP access logs:</strong> ordinarily deleted
                            within 30 days.
                        </li>
                        <li>
                            <strong>Security-related records:</strong> may be
                            retained longer where reasonably necessary to
                            investigate or document abuse or a security
                            incident.
                        </li>
                        <li>
                            <strong>Email or other communications:</strong>{' '}
                            retained only for as long as reasonably necessary to
                            respond to the communication, maintain relevant
                            records, or satisfy applicable legal requirements.
                        </li>
                    </ul>
                    <p>
                        When personal data is no longer reasonably necessary for
                        the applicable purpose, it is deleted or anonymized
                        where practical.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>9. GDPR Rights</h3>
                    <p>
                        If you are located in the European Economic Area or
                        another jurisdiction where the GDPR applies, you may
                        have rights including the right to:
                    </p>
                    <ul>
                        <li>request access to personal data concerning you;</li>
                        <li>request correction of inaccurate personal data;</li>
                        <li>request deletion of personal data;</li>
                        <li>request restriction of processing;</li>
                        <li>
                            object to processing based on legitimate interests;
                        </li>
                        <li>
                            receive certain personal data in a portable format
                            where applicable;
                        </li>
                        <li>
                            withdraw consent where processing is based on
                            consent; and
                        </li>
                        <li>
                            lodge a complaint with an applicable data protection
                            supervisory authority.
                        </li>
                    </ul>
                    <p>
                        Because Venera does not maintain user accounts and
                        retains very limited information, we may not always be
                        able to identify server-log information as belonging to
                        a particular person without additional information such
                        as the relevant IP address and approximate access time.
                    </p>
                    <p>
                        Requests may be submitted to{' '}
                        <a href="mailto:ben@oneill.sh">ben@oneill.sh</a>.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>10. International Users</h3>
                    <p>Venera is operated from the United States.</p>
                    <p>
                        If you access Venera from outside the United States,
                        technical information such as your IP address may
                        therefore be processed in the United States or in other
                        jurisdictions where Venera&rsquo;s infrastructure
                        providers operate.
                    </p>
                    <p>
                        Venera seeks to limit such processing to information
                        reasonably necessary to provide and secure the Service.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>11. California Privacy Rights</h3>
                    <p>
                        This section applies to California residents to the
                        extent the CCPA or other applicable California privacy
                        law applies to Venera.
                    </p>

                    <h4>Categories of Personal Information</h4>
                    <p>
                        During the preceding 12 months, Venera may have
                        processed the following categories of personal
                        information:
                    </p>
                    <p>
                        <strong>Identifiers</strong>
                    </p>
                    <ul>
                        <li>IP address.</li>
                        <li>
                            Source: automatically generated when a user connects
                            to the Service.
                        </li>
                        <li>
                            Purpose: operation, security, abuse prevention, and
                            diagnostics.
                        </li>
                        <li>
                            Sold or shared for cross-context behavioral
                            advertising: <strong>No</strong>.
                        </li>
                    </ul>
                    <p>
                        <strong>Geolocation Information</strong>
                    </p>
                    <ul>
                        <li>
                            A municipality, latitude/longitude coordinates, or
                            device-provided location submitted by a user for
                            Venera functionality.
                        </li>
                        <li>
                            Source: provided directly by the user or, with
                            permission, by the user&rsquo;s device.
                        </li>
                        <li>
                            Purpose: astronomical calculations, weather
                            information, and observing recommendations.
                        </li>
                        <li>
                            Retention: processed transiently and not retained by
                            Venera.
                        </li>
                        <li>
                            Sold or shared for cross-context behavioral
                            advertising: <strong>No</strong>.
                        </li>
                    </ul>

                    <h4>Sale and Sharing of Personal Information</h4>
                    <p>
                        <strong>
                            Venera does not sell personal information.
                        </strong>
                    </p>
                    <p>
                        <strong>
                            Venera does not share personal information for
                            cross-context behavioral advertising.
                        </strong>
                    </p>
                    <p>
                        Venera does not receive money or other consideration in
                        exchange for users&rsquo; personal information.
                    </p>
                    <p>
                        Because Venera does not sell or share personal
                        information for these purposes, there is currently no
                        sale or sharing from which a user needs to opt out.
                    </p>

                    <h4>Sensitive Personal Information</h4>
                    <p>
                        Precise geolocation may be treated as sensitive personal
                        information under California law.
                    </p>
                    <p>
                        Where Venera processes precise location information, it
                        is used only to provide functionality specifically
                        requested by the user and is not retained by Venera or
                        used to build a user profile.
                    </p>
                    <p>
                        Venera does not use or disclose sensitive personal
                        information for purposes that require offering a
                        separate right to limit such processing.
                    </p>

                    <h4>California Consumer Rights</h4>
                    <p>
                        Where applicable, California residents may have rights
                        to:
                    </p>
                    <ul>
                        <li>
                            know what personal information is collected, used,
                            disclosed, sold, or shared;
                        </li>
                        <li>request access to personal information;</li>
                        <li>request deletion of personal information;</li>
                        <li>
                            request correction of inaccurate personal
                            information;
                        </li>
                        <li>
                            opt out of the sale or sharing of personal
                            information;
                        </li>
                        <li>
                            limit certain uses or disclosures of sensitive
                            personal information; and
                        </li>
                        <li>
                            exercise privacy rights without unlawful
                            discrimination.
                        </li>
                    </ul>
                    <p>
                        Requests may be submitted by email to{' '}
                        <a href="mailto:ben@oneill.sh">ben@oneill.sh</a>.
                    </p>
                    <p>
                        Because Venera operates exclusively online, email is the
                        designated method for submitting privacy requests.
                    </p>
                    <p>
                        Venera may request information reasonably necessary to
                        verify that a requester is the person associated with
                        the personal information at issue.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>12. Global Privacy Control</h3>
                    <p>
                        Venera does not sell personal information or share
                        personal information for cross-context behavioral
                        advertising.
                    </p>
                    <p>
                        Accordingly, Global Privacy Control and similar browser
                        preference signals do not alter Venera&rsquo;s current
                        data practices: there is no sale or applicable sharing
                        to opt out of.
                    </p>
                    <p>
                        If Venera&rsquo;s data practices change in a manner that
                        makes such opt-out rights applicable, supported opt-out
                        preference signals will be honored as required by
                        applicable law.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>13. Children&rsquo;s Privacy</h3>
                    <p>
                        Venera is a general-purpose astronomy application and is
                        not designed to collect personal information from
                        children.
                    </p>
                    <p>
                        Venera does not knowingly sell or share the personal
                        information of users under 16 years of age.
                    </p>
                    <p>
                        If we learn that personal information from a child has
                        been retained contrary to applicable law, we will take
                        reasonable steps to delete it.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>14. Disclosure of Information</h3>
                    <p>Venera may disclose limited personal information:</p>
                    <ul>
                        <li>
                            to hosting, networking, or infrastructure providers
                            where necessary to operate the Service;
                        </li>
                        <li>
                            where reasonably necessary to investigate malicious
                            activity or protect the security of Venera or
                            others;
                        </li>
                        <li>
                            where required by applicable law, court order, or
                            valid legal process; or
                        </li>
                        <li>
                            where necessary to establish, exercise, or defend
                            legal claims.
                        </li>
                    </ul>
                    <p>
                        Venera does not sell user information to data brokers,
                        advertisers, or other third parties.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>15. Security</h3>
                    <p>
                        Reasonable technical and organizational safeguards are
                        used to protect information processed by Venera.
                    </p>
                    <p>
                        However, no Internet service or method of electronic
                        storage can guarantee absolute security.
                    </p>
                    <p>
                        Venera limits retained personal information in part to
                        reduce the consequences of unauthorized access.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>16. Do Not Track</h3>
                    <p>
                        Some browsers transmit &ldquo;Do Not Track&rdquo;
                        signals.
                    </p>
                    <p>
                        Because Venera does not engage in cross-site behavioral
                        tracking or targeted advertising, it does not maintain a
                        separate response mechanism for Do Not Track signals.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>17. Changes to This Privacy Policy</h3>
                    <p>
                        This Privacy Policy may be updated when Venera&rsquo;s
                        functionality, data practices, infrastructure, or
                        applicable legal requirements change.
                    </p>
                    <p>
                        The effective date at the top of this Policy will be
                        updated when material changes are made.
                    </p>
                    <p>
                        Where required by law, additional notice will be
                        provided before materially different processing of
                        previously collected personal information begins.
                    </p>
                </section>

                <section className="policy-section">
                    <h3>18. Contact</h3>
                    <p>
                        Questions, concerns, or requests concerning this Privacy
                        Policy or personal data processed by Venera may be
                        directed to:
                    </p>
                    <p>
                        <strong>Ben O&rsquo;Neill</strong>
                        <br />
                        <a href="mailto:ben@oneill.sh">ben@oneill.sh</a>
                    </p>
                </section>
            </div>
        </div>
    )
}
