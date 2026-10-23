# FixMyCampus mobile

Expo (React Native) app for students and faculty: sign in, report an issue with photos and location,
follow your tickets, and chat with the campus assistant. Staff and admin tools stay on the web app.

## Run it

1. Start the backend (`docker compose up -d` or `uvicorn` in `backend/`, see `docs/SETUP.md`).
2. Create `mobile/.env.local` (git-ignored):

   ```
   EXPO_PUBLIC_SUPABASE_URL=...        # same values as frontend/.env
   EXPO_PUBLIC_SUPABASE_ANON_KEY=...
   EXPO_PUBLIC_WEB_URL=http://localhost:5173
   # EXPO_PUBLIC_API_BASE_URL=https://...   only for a deployed backend
   ```

   In development the app finds the backend on port 8000 of the machine running `expo start`, so the iOS
   Simulator, the Android emulator and a real phone on the same Wi-Fi all work without changes. The backend
   must listen on all interfaces (`uvicorn ... --host 0.0.0.0`).
3. `npm install`, then `npx expo start`:
   - **Phone (Android or iPhone):** install Expo Go and scan the QR code. Same Wi-Fi as the Mac.
   - **iOS Simulator:** press `i` (needs Xcode).
   - **Android emulator:** press `a` (needs Android Studio with an emulator created).

Email links (confirm sign-up, reset password) open the web app at `EXPO_PUBLIC_WEB_URL`.

## Layout

- `src/app/` — screens (Expo Router). `(auth)` is shown when signed out, `(tabs)` and `ticket/[ref]` when signed in.
- `src/lib/` — API client, auth, and helpers. `api.ts`, `tickets.ts`, `places.ts`, `account.ts` and `assistant.ts`
  are copies of the web app's `frontend/src/lib` files; keep them in step when the API changes.
- `src/components/ui` — shared building blocks (Screen, Button, Card, Badge, TextField...).

Checks: `npx tsc --noEmit`.
