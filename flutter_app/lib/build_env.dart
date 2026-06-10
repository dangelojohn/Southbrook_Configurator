// SPDX-License-Identifier: LGPL-3.0-only
//
// Build-time channel flag. Set via --dart-define=STAGING=true when compiling
// the /app-staging/ bundle; defaults to false (the production /app/ bundle).
// Surfaced in the UI as a top banner + auto-expanded server URL field so
// testers know which channel they're on and can re-target the backend.

class BuildEnv {
  static const bool staging = bool.fromEnvironment('STAGING', defaultValue: false);
  static String get channelLabel => staging ? 'STAGING' : 'PRODUCTION';
}
