# BeeThere browser extension

This project builds the BeeThere Manifest V3 Chrome extension.

## Requirements

- Node.js 22.12 or newer
- npm
- Google Chrome for manual use

## Install dependencies

From the `extension` directory, run:

```shell
npm ci
```

## Build

Set the BeeThere API origin when you build:

```shell
BEE_THERE_API_BASE_URL=http://127.0.0.1:8000 npm run build
```

Use only the origin, without an API path. The build writes this value into the
extension and grants host permission only to that origin. The unpacked
extension is written to `extension/dist`.

## Find events

Search matches event titles only. Category choices use OR; title, categories,
and dates combine with AND. The server filters and sorts each 20-event page.
Scroll the results to load all matches. A failed later page can be retried
without losing earlier matches.

Dates use Europe/Belgrade, not the browser timezone. Custom ranges include
both dates and overlapping events. Use `DD MMM YYYY` in date fields. Calendar
arrow keys move by day or week; Page Up and Page Down change months. Past dates
cannot be selected. Invalid or incomplete dates keep the last applied choice.

Search, categories, dates, and Favorites only are inside **Show filters**.
They start hidden. Hiding filters does not stop them from applying.
The extension saves these choices locally. Relative dates recalculate when
opened. Partly expired custom ranges start today; wholly expired dates reset
with a notice. Clear all resets these choices, including Favorites only. It
does not remove marked favorites or change the theme.

## Favorites

Use the star on any event card to add or remove a favorite. The star is always
visible. An outline means not marked; a filled star means marked. Open
**Show filters** and turn **Favorites only** on to browse marked events with the
same search, categories, and dates.

Only event IDs are saved in local browser storage (`bee-there-favorites`).
There are no saved event snapshots, accounts, sync, added permissions, or
artificial favorite limits. Event details always come from the API. Missing
or past events stay marked. If the same ID returns, it is still a favorite.
Clearing browser or extension storage removes these local choices.

All event searches use `QUERY /api/events` with a JSON body containing
`from`, optional `to`, `q`, and `category` (an array), plus `limit` and `offset`.
Normal browsing omits `event_ids`. Favorites-only searches include all marked
IDs in `event_ids`; pages contain 20 results. No request is needed when
Favorites only is on and there are no marked IDs.

Empty states distinguish no saved favorites, no upcoming favorites available,
and no favorites matching the current filters. Network errors offer retry and
keep choices. A storage read error disables favorite actions until a successful
retry; it never replaces saved IDs. A write error keeps the previous state and
announces the failure. Favorite announcements are separate from result errors.

## Google Calendar

Use the calendar-plus icon beside the star to open a Google Calendar draft in
another tab. Review the draft and save it there. No favorite is required.

Known start and end times use the Novi Sad schedule (`Europe/Belgrade`). If the
end is unknown, the draft is all-day on the Novi Sad start date. Its description
starts with the actual start time and explains the all-day fallback. Missing
venues leave Location empty. The export includes the source link and a no-sync
notice, but not the event summary.

This is a one-time copy of the displayed details. BeeThere does not refresh on
click, track saving, prevent duplicates, or update entries later. Google controls
sign-in and default reminders. Recovery through sign-in is not verified; if the
draft is lost, sign in and use the icon again.

## Test

```shell
npm test
```

The tests build the extension, load it in Puppeteer's bundled Chromium, open
the real toolbar action popup, and check the popup shell. The release smoke
test starts the real backend, extracts the generated ZIP, installs that clean
bundle, and completes the upcoming-events journey. Discovery tests also check
real-server title matching, category OR, overlapping dates, and all result pages.
Pure date tests cover Belgrade day boundaries across both DST changes.
Favorites unit and browser tests cover local IDs, storage failures, QUERY
bodies and pagination, fresh returning details, focus, and narrow layouts in
both themes. Calendar tests cover timed and all-day links, DST and date
boundaries, URL encoding, independent favorite/error states, tooltip dismissal,
keyboard and touch activation, and narrow layouts. Google DNS is blocked in the
browser suite; handoff tests check the new tab, not Google's editor or saving.

## Create a Chrome release

Set the production API origin and run:

```shell
BEE_THERE_API_BASE_URL=https://api.example.com npm run release
```

The command performs a clean build and writes
`extension/release/bee-there-chrome-<version>.zip`, using the version from
`src/manifest.json`. The ZIP contains only runtime files, with `manifest.json`
at its root. The manifest omits
`content_security_policy`, so Chrome applies the default Manifest V3 policy.

Before sharing or uploading a release, extract the ZIP and complete this
manual review:

- Load the extracted directory through `chrome://extensions` and open the real
  toolbar popup.
- Confirm the manifest has only the toolbar popup and the expected API-origin
  host permission.
- Check the popup size and scrolling with no events and with a long event list.
- Check narrow content near 320 CSS pixels. Confirm that text wraps and no
  control is clipped or requires horizontal scrolling.
- Check long titles, summaries, locations, source names, and unbroken words.
- Use `Tab` and `Shift+Tab` to inspect focus order and visible focus. Activate
  source links with `Enter`, and retry with both `Enter` and `Space`.
- Check loading, event, empty, and error states in both light and dark browser
  themes.

## Install in Chrome

1. Build the extension.
2. Open `chrome://extensions` in Chrome.
3. Enable **Developer mode**.
4. Select **Load unpacked**.
5. Select the generated `extension/dist` directory.
6. Select the BeeThere toolbar action to open the popup. You can pin the
   action from Chrome's Extensions menu.
