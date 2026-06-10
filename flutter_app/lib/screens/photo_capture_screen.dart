// SPDX-License-Identifier: LGPL-3.0-only

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../api_client.dart';
import '../theme.dart';

class PhotoCaptureScreen extends StatefulWidget {
  final SouthbrookApiClient client;
  final int projectId;

  const PhotoCaptureScreen({
    super.key,
    required this.client,
    required this.projectId,
  });

  @override
  State<PhotoCaptureScreen> createState() => _PhotoCaptureScreenState();
}

class _PhotoCaptureScreenState extends State<PhotoCaptureScreen> {
  final _picker = ImagePicker();
  File? _photo;
  String? _error;
  bool _busy = false;

  Future<void> _pickFrom(ImageSource source) async {
    setState(() => _error = null);
    try {
      final picked = await _picker.pickImage(
        source: source,
        imageQuality: 85,
        maxWidth: 4096,
      );
      if (picked == null) return;
      setState(() => _photo = File(picked.path));
    } catch (e) {
      setState(() => _error = '$e');
    }
  }

  Future<void> _upload() async {
    final photo = _photo;
    if (photo == null) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      // Idempotency: project id + last-modified ms — same file uploaded twice
      // by accident still posts once.
      final stat = await photo.stat();
      final idempotencyKey =
          'photo-${widget.projectId}-${stat.modified.millisecondsSinceEpoch}';
      await widget.client.uploadPhoto(
        widget.projectId,
        photo,
        idempotencyKey: idempotencyKey,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text("Photo uploaded — we'll analyze it now."),
      ));
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      setState(() => _error = e.message.isNotEmpty ? e.message : e.code);
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add a kitchen photo')),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: _photo == null
                  ? _Empty(onCamera: () => _pickFrom(ImageSource.camera),
                          onGallery: () => _pickFrom(ImageSource.gallery))
                  : _Preview(file: _photo!),
            ),
            if (_error != null)
              Container(
                width: double.infinity,
                margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
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
            if (_photo != null)
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _busy ? null : () =>
                            setState(() => _photo = null),
                        icon: const Icon(Icons.refresh, size: 18),
                        label: const Text('Choose different'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton.icon(
                        onPressed: _busy ? null : _upload,
                        icon: _busy
                            ? const SizedBox(
                                width: 16, height: 16,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white,
                                ),
                              )
                            : const Icon(Icons.cloud_upload_outlined,
                                size: 18),
                        label: Text(_busy ? 'Uploading…' : 'Upload'),
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  final VoidCallback onCamera;
  final VoidCallback onGallery;
  const _Empty({required this.onCamera, required this.onGallery});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.add_photo_alternate_outlined,
                size: 80, color: SouthbrookColors.inkSoft),
            const SizedBox(height: 16),
            const Text(
              'Show us your kitchen',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: SouthbrookColors.ink,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Wide shots work best — try to capture the walls and any '
              'appliances already in place.',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: SouthbrookColors.inkSoft,
              ),
            ),
            const SizedBox(height: 32),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: onCamera,
                icon: const Icon(Icons.camera_alt),
                label: const Text('Take a photo'),
              ),
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: onGallery,
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('Choose from library'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Preview extends StatelessWidget {
  final File file;
  const _Preview({required this.file});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Image.file(file, fit: BoxFit.contain),
      ),
    );
  }
}
