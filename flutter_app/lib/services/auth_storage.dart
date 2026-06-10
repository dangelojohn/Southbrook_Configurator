// SPDX-License-Identifier: LGPL-3.0-only
//
// Persistence for the post-login auth bundle: base URL + API key.
// Wraps flutter_secure_storage so the rest of the app doesn't need to
// know which key holds what.

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthStorage {
  static const _kApiKey = 'api_key';
  static const _kBaseUri = 'base_uri';
  static const _kEmail = 'email';

  static const _storage = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  Future<AuthSnapshot?> load() async {
    final key = await _storage.read(key: _kApiKey);
    final base = await _storage.read(key: _kBaseUri);
    if (key == null || base == null) return null;
    final email = await _storage.read(key: _kEmail);
    return AuthSnapshot(baseUri: base, apiKey: key, email: email);
  }

  Future<void> save({
    required String baseUri,
    required String apiKey,
    String? email,
  }) async {
    await _storage.write(key: _kBaseUri, value: baseUri);
    await _storage.write(key: _kApiKey, value: apiKey);
    if (email != null) {
      await _storage.write(key: _kEmail, value: email);
    }
  }

  Future<void> clear() async {
    await _storage.delete(key: _kApiKey);
    await _storage.delete(key: _kBaseUri);
    await _storage.delete(key: _kEmail);
  }
}

class AuthSnapshot {
  final String baseUri;
  final String apiKey;
  final String? email;
  AuthSnapshot({required this.baseUri, required this.apiKey, this.email});
}
