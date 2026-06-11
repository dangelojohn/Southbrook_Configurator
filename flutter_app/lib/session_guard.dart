// SPDX-License-Identifier: LGPL-3.0-only
//
// App-wide session recovery. Any API call that comes back 401 (stale or
// revoked key) routes the user back to the login screen exactly once,
// regardless of which screen triggered it — so a mid-session expiry on the
// detail / concept / approve screens recovers cleanly instead of surfacing a
// dead error. Wired by setting SouthbrookApiClient.onUnauthorized on every
// post-login client (see main.dart and login_screen.dart).

import 'package:flutter/material.dart';

import 'screens/login_screen.dart';
import 'services/auth_storage.dart';

/// Attached to MaterialApp so the guard can navigate without a BuildContext.
final GlobalKey<NavigatorState> appNavigatorKey = GlobalKey<NavigatorState>();

class SessionGuard {
  static bool _expiring = false;

  /// Clear the stored key and reset the stack to LoginScreen. Re-entrant
  /// calls (several in-flight requests all 401) collapse into one redirect.
  static Future<void> expire(AuthStorage storage) async {
    if (_expiring) return;
    _expiring = true;
    try {
      await storage.clear();
      final nav = appNavigatorKey.currentState;
      if (nav != null) {
        await nav.pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => LoginScreen(storage: storage)),
          (route) => false,
        );
      }
    } finally {
      _expiring = false;
    }
  }
}
