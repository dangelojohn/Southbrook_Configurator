// SPDX-License-Identifier: LGPL-3.0-only
//
// Southbrook Kitchen — mobile customer app.
// Minimal skeleton: login screen + project list. The full UI (photo
// upload, concept review, approval) reuses api_client.dart and lands
// after the contract (G6) gets a real Odoo /api/v1 implementation
// behind it.

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api_client.dart';

void main() {
  runApp(const SouthbrookApp());
}

class SouthbrookApp extends StatelessWidget {
  const SouthbrookApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Southbrook Kitchen',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1E3A5F)),
        useMaterial3: true,
      ),
      home: const LoginScreen(),
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _baseUri = TextEditingController(
    text: 'https://southbrookcabinetry.space',
  );
  final _storage = const FlutterSecureStorage();
  String? _error;
  bool _busy = false;

  Future<void> _doLogin() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final client = SouthbrookApiClient(Uri.parse(_baseUri.text));
      await client.login(_email.text.trim(), _password.text);
      await _storage.write(key: 'api_key', value: client.apiKey);
      if (mounted) {
        Navigator.of(context).pushReplacement(MaterialPageRoute(
          builder: (_) => ProjectListScreen(client: client),
        ));
      }
    } on ApiException catch (e) {
      setState(() => _error = '${e.code}: ${e.message}');
    } catch (e) {
      setState(() => _error = 'Login failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Southbrook Kitchen')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            TextField(
              controller: _baseUri,
              decoration: const InputDecoration(labelText: 'Server'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _email,
              decoration: const InputDecoration(labelText: 'Email'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _password,
              obscureText: true,
              decoration: const InputDecoration(labelText: 'Password'),
            ),
            const SizedBox(height: 24),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Text(_error!, style: const TextStyle(color: Colors.red)),
              ),
            ElevatedButton(
              onPressed: _busy ? null : _doLogin,
              child: _busy
                  ? const CircularProgressIndicator()
                  : const Text('Sign in'),
            ),
          ],
        ),
      ),
    );
  }
}

class ProjectListScreen extends StatefulWidget {
  final SouthbrookApiClient client;
  const ProjectListScreen({super.key, required this.client});

  @override
  State<ProjectListScreen> createState() => _ProjectListScreenState();
}

class _ProjectListScreenState extends State<ProjectListScreen> {
  late Future<List<dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.client.listProjects();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Kitchen Projects')),
      body: FutureBuilder<List<dynamic>>(
        future: _future,
        builder: (_, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snap.hasError) {
            return Center(child: Text('Error: ${snap.error}'));
          }
          final projects = snap.data ?? const [];
          if (projects.isEmpty) {
            return const Center(child: Text('No projects yet.'));
          }
          return ListView.separated(
            itemCount: projects.length,
            separatorBuilder: (_, __) => const Divider(),
            itemBuilder: (_, i) {
              final p = projects[i] as Map<String, dynamic>;
              return ListTile(
                title: Text(p['name'] as String? ?? '—'),
                subtitle: Text('${p['code']} · ${p['state']}'),
                trailing: Text('${p['concept_count'] ?? 0} concepts'),
              );
            },
          );
        },
      ),
    );
  }
}
