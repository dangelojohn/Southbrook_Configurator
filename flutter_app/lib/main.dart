// SPDX-License-Identifier: LGPL-3.0-only
//
// Southbrook Kitchen — customer mobile app entry point.
// Boot resolves the auth state from flutter_secure_storage and routes
// to LoginScreen or ProjectListScreen accordingly.

import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import 'api_client.dart';
import 'screens/login_screen.dart';
import 'screens/project_list_screen.dart';
import 'services/auth_storage.dart';
import 'theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Force the semantics tree on. Without this, Flutter web only emits
  // <flt-semantics> when an assistive tech is detected — so DevTools
  // and automated test runners see an empty a11y tree even though the
  // app has the right Semantics widgets in place.
  SemanticsBinding.instance.ensureSemantics();
  runApp(const SouthbrookApp());
}

class SouthbrookApp extends StatelessWidget {
  const SouthbrookApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Southbrook Kitchen',
      theme: buildSouthbrookTheme(),
      debugShowCheckedModeBanner: false,
      home: const _BootGate(),
    );
  }
}

class _BootGate extends StatefulWidget {
  const _BootGate();

  @override
  State<_BootGate> createState() => _BootGateState();
}

class _BootGateState extends State<_BootGate> {
  final _storage = AuthStorage();
  late final Future<Widget> _initialScreen;

  @override
  void initState() {
    super.initState();
    _initialScreen = _resolve();
  }

  Future<Widget> _resolve() async {
    final snapshot = await _storage.load();
    if (snapshot == null) {
      return LoginScreen(storage: _storage);
    }
    final client = SouthbrookApiClient(
      Uri.parse(snapshot.baseUri),
      apiKey: snapshot.apiKey,
    );
    // We *could* probe /api/v1/me to validate the key here, but a stale
    // key still fails gracefully on the project list — the user lands
    // back at the login screen via the 401 fallback below. Skipping the
    // probe saves a round-trip on every cold start.
    return ProjectListScreen(client: client, storage: _storage);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Widget>(
      future: _initialScreen,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return Scaffold(
            backgroundColor: SouthbrookColors.linen,
            body: Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    height: 56,
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    decoration: BoxDecoration(
                      color: SouthbrookColors.walnut,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Center(
                      child: Text(
                        'SOUTHBROOK KITCHEN',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 2.0,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  const CircularProgressIndicator(
                    color: SouthbrookColors.walnut,
                  ),
                ],
              ),
            ),
          );
        }
        return snap.data ?? LoginScreen(storage: _storage);
      },
    );
  }
}
