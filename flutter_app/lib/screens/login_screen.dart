// SPDX-License-Identifier: LGPL-3.0-only

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../build_env.dart';
import '../services/auth_storage.dart';
import '../session_guard.dart';
import '../theme.dart';
import 'project_list_screen.dart';

class LoginScreen extends StatefulWidget {
  final AuthStorage storage;
  final String? prefillBaseUri;
  final String? prefillEmail;

  const LoginScreen({
    super.key,
    required this.storage,
    this.prefillBaseUri,
    this.prefillEmail,
  });

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  late final TextEditingController _email;
  final _password = TextEditingController();
  late final TextEditingController _baseUri;

  String? _error;
  bool _busy = false;
  // Auto-expand server URL field on staging builds so testers can re-target
  // the backend without hunting for the toggle.
  bool _showAdvanced = BuildEnv.staging;

  @override
  void initState() {
    super.initState();
    _email = TextEditingController(text: widget.prefillEmail ?? '');
    _baseUri = TextEditingController(
      text: widget.prefillBaseUri ?? 'https://southbrookcabinetry.space',
    );
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _baseUri.dispose();
    super.dispose();
  }

  Future<void> _doLogin() async {
    if (_email.text.trim().isEmpty || _password.text.isEmpty) {
      setState(() => _error = 'Email and password are required');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final base = _baseUri.text.trim();
      final client = SouthbrookApiClient(Uri.parse(base));
      await client.login(_email.text.trim(), _password.text);
      await widget.storage.save(
        baseUri: base,
        apiKey: client.apiKey!,
        email: _email.text.trim(),
      );
      // Now that we're authenticated, route any later 401 back to login.
      client.onUnauthorized = () => SessionGuard.expire(widget.storage);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(
        builder: (_) => ProjectListScreen(
          client: client,
          storage: widget.storage,
        ),
      ));
    } on ApiException catch (e) {
      setState(() => _error = e.message.isNotEmpty ? e.message : e.code);
    } catch (e) {
      setState(() => _error = 'Login failed: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (BuildEnv.staging) ...[
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 8),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF3C7),
                        border: Border.all(color: const Color(0xFFD97706)),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.science_outlined,
                              size: 16, color: Color(0xFF92400E)),
                          SizedBox(width: 8),
                          Text(
                            'STAGING — pre-release channel',
                            style: TextStyle(
                              color: Color(0xFF92400E),
                              fontSize: 12,
                              fontWeight: FontWeight.w600,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                  const SizedBox(height: 32),
                  Container(
                    height: 56,
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
                  const SizedBox(height: 12),
                  const Text(
                    'Sign in to review your kitchen project.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: SouthbrookColors.inkSoft,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 32),
                  TextField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    enableSuggestions: false,
                    textInputAction: TextInputAction.next,
                    decoration: const InputDecoration(
                      labelText: 'Email',
                      hintText: 'you@example.com',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _password,
                    obscureText: true,
                    textInputAction: TextInputAction.done,
                    onSubmitted: (_) => _busy ? null : _doLogin(),
                    decoration: const InputDecoration(labelText: 'Password'),
                  ),
                  const SizedBox(height: 16),
                  if (_error != null)
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: SouthbrookColors.danger.withValues(alpha: 0.08),
                        border: Border.all(
                          color: SouthbrookColors.danger.withValues(alpha: 0.3),
                        ),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        _error!,
                        style: const TextStyle(
                          color: SouthbrookColors.danger,
                          fontSize: 13,
                        ),
                      ),
                    ),
                  if (_error != null) const SizedBox(height: 16),
                  SizedBox(
                    height: 52,
                    child: ElevatedButton(
                      onPressed: _busy ? null : _doLogin,
                      child: _busy
                          ? const SizedBox(
                              width: 22, height: 22,
                              child: CircularProgressIndicator(
                                strokeWidth: 2.5,
                                color: Colors.white,
                              ),
                            )
                          : const Text('Sign in'),
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: () =>
                        setState(() => _showAdvanced = !_showAdvanced),
                    child: Text(_showAdvanced
                        ? 'Hide advanced'
                        : 'Server URL (advanced)'),
                  ),
                  if (_showAdvanced)
                    TextField(
                      controller: _baseUri,
                      keyboardType: TextInputType.url,
                      autocorrect: false,
                      decoration: const InputDecoration(
                        labelText: 'Server base URL',
                        hintText: 'https://southbrookcabinetry.space',
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
