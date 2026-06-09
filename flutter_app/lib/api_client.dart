// SPDX-License-Identifier: LGPL-3.0-only
//
// Southbrook Flutter ↔ Odoo API client — reference implementation of
// docs/api_contracts/flutter_odoo_contract.md (schema
// 'southbrook.flutter.api.v1').
//
// One client instance per logged-in user. Holds the API key in memory;
// the caller is responsible for persisting it to flutter_secure_storage.
//
// All endpoints return decoded JSON. Errors raise ApiException whose
// `code` is the machine-string from the error envelope (§4).

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

const String _kSchema = 'southbrook.flutter.api.v1';

class ApiException implements Exception {
  final int statusCode;
  final String code;
  final String message;
  ApiException(this.statusCode, this.code, this.message);

  @override
  String toString() => 'ApiException($statusCode $code): $message';
}

class SouthbrookApiClient {
  final Uri baseUri;
  String? apiKey;

  SouthbrookApiClient(this.baseUri, {this.apiKey});

  Map<String, String> _headers({String? idempotencyKey, bool requireKey = true}) {
    final h = <String, String>{
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    };
    if (requireKey) {
      if (apiKey == null) {
        throw ApiException(401, 'no_api_key', 'API key not set');
      }
      h['X-Api-Key'] = apiKey!;
    }
    if (idempotencyKey != null) {
      h['Idempotency-Key'] = idempotencyKey;
    }
    return h;
  }

  Uri _u(String path) => baseUri.replace(path: '${baseUri.path}$path');

  Future<Map<String, dynamic>> _decode(http.Response resp) async {
    Map<String, dynamic> body;
    try {
      body = jsonDecode(resp.body) as Map<String, dynamic>;
    } on FormatException {
      throw ApiException(resp.statusCode, 'malformed_response', resp.body);
    }
    if (resp.statusCode >= 400) {
      throw ApiException(
        resp.statusCode,
        body['error'] as String? ?? 'unknown_error',
        body['message'] as String? ?? '',
      );
    }
    if (body['schema'] != _kSchema) {
      throw ApiException(
        500, 'schema_mismatch',
        'expected $_kSchema got ${body['schema']}',
      );
    }
    return body;
  }

  // §3.1
  Future<Map<String, dynamic>> login(String email, String password) async {
    final resp = await http.post(
      _u('/api/v1/auth/login'),
      headers: _headers(requireKey: false),
      body: jsonEncode({'email': email, 'password': password}),
    );
    final body = await _decode(resp);
    apiKey = body['api_key'] as String;
    return body;
  }

  // §3.1
  Future<Map<String, dynamic>> me() async {
    final resp = await http.get(_u('/api/v1/me'), headers: _headers());
    return _decode(resp);
  }

  // §3.2
  Future<List<dynamic>> listProjects() async {
    final resp = await http.get(
      _u('/api/v1/kitchen-projects'), headers: _headers(),
    );
    final body = await _decode(resp);
    return body['projects'] as List<dynamic>;
  }

  // §3.3
  Future<Map<String, dynamic>> projectDetail(int projectId) async {
    final resp = await http.get(
      _u('/api/v1/kitchen-projects/$projectId'), headers: _headers(),
    );
    final body = await _decode(resp);
    return body['project'] as Map<String, dynamic>;
  }

  // §3.4
  Future<Map<String, dynamic>> uploadPhoto(
    int projectId,
    File photo, {
    String promptTemplateCode = 'default_v1',
    String? idempotencyKey,
  }) async {
    final req = http.MultipartRequest(
      'POST', _u('/api/v1/kitchen-projects/$projectId/photos'),
    );
    req.headers.addAll(_headers(idempotencyKey: idempotencyKey)
      ..remove('Content-Type'));
    req.fields['prompt_template_code'] = promptTemplateCode;
    req.files.add(await http.MultipartFile.fromPath('photo', photo.path));
    final streamed = await req.send();
    final resp = await http.Response.fromStream(streamed);
    return _decode(resp);
  }

  // §3.5
  Future<List<dynamic>> listConcepts(int projectId) async {
    final resp = await http.get(
      _u('/api/v1/kitchen-projects/$projectId/concepts'),
      headers: _headers(),
    );
    final body = await _decode(resp);
    return body['concepts'] as List<dynamic>;
  }

  // §3.6
  Future<Map<String, dynamic>> selectConcept(
    int projectId, int optionId,
    {String? idempotencyKey}) async {
    final resp = await http.post(
      _u('/api/v1/kitchen-projects/$projectId/concepts/$optionId/select'),
      headers: _headers(idempotencyKey: idempotencyKey),
      body: jsonEncode({}),
    );
    return _decode(resp);
  }

  // §3.7
  Future<Map<String, dynamic>> approveProject(
    int projectId, {String? notes, String? idempotencyKey}) async {
    final resp = await http.post(
      _u('/api/v1/kitchen-projects/$projectId/approve'),
      headers: _headers(idempotencyKey: idempotencyKey),
      body: jsonEncode({if (notes != null) 'notes': notes}),
    );
    return _decode(resp);
  }
}
