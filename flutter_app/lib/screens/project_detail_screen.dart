// SPDX-License-Identifier: LGPL-3.0-only

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models/project.dart';
import '../services/auth_storage.dart';
import '../theme.dart';
import 'approval_screen.dart';
import 'concept_review_screen.dart';
import 'photo_capture_screen.dart';

class ProjectDetailScreen extends StatefulWidget {
  final SouthbrookApiClient client;
  final AuthStorage storage;
  final int projectId;

  const ProjectDetailScreen({
    super.key,
    required this.client,
    required this.storage,
    required this.projectId,
  });

  @override
  State<ProjectDetailScreen> createState() => _ProjectDetailScreenState();
}

class _ProjectDetailScreenState extends State<ProjectDetailScreen> {
  Project? _project;
  String? _error;
  bool _busy = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final raw = await widget.client.projectDetail(widget.projectId);
      if (!mounted) return;
      setState(() => _project = Project.fromJson(raw));
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message.isNotEmpty ? e.message : e.code);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openPhotoCapture() async {
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(
      builder: (_) => PhotoCaptureScreen(
        client: widget.client,
        projectId: widget.projectId,
      ),
    ));
    if (changed == true) await _load();
  }

  Future<void> _openConcepts() async {
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(
      builder: (_) => ConceptReviewScreen(
        client: widget.client,
        projectId: widget.projectId,
        currentlySelectedId: _project?.selectedOptionId,
      ),
    ));
    if (changed == true) await _load();
  }

  Future<void> _openApproval() async {
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(
      builder: (_) => ApprovalScreen(
        client: widget.client,
        projectId: widget.projectId,
      ),
    ));
    if (changed == true) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final p = _project;
    return Scaffold(
      appBar: AppBar(
        title: Text(p?.code ?? 'Project'),
      ),
      body: _busy
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _ErrorPanel(message: _error!, onRetry: _load)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      _Header(project: p!),
                      const SizedBox(height: 24),
                      _StepCard(
                        index: 1,
                        title: 'Upload a kitchen photo',
                        subtitle: p.photoCount > 0
                            ? '${p.photoCount} photo'
                              '${p.photoCount == 1 ? '' : 's'} uploaded.'
                              ' Add more if helpful.'
                            : 'Show us your room. Our AI reads the wall '
                              'shapes and appliance footprints from the '
                              'photo to seed the design.',
                        actionLabel: p.photoCount > 0
                            ? 'Upload another photo'
                            : 'Take or pick a photo',
                        actionIcon: Icons.camera_alt_outlined,
                        enabled: p.canUploadPhoto || p.state == 'awaiting_customer',
                        onAction: _openPhotoCapture,
                        complete: p.hasAiAnalysis,
                      ),
                      const SizedBox(height: 12),
                      _StepCard(
                        index: 2,
                        title: 'Review design concepts',
                        subtitle: p.designOptionCount > 0
                            ? '${p.designOptionCount} concept'
                              '${p.designOptionCount == 1 ? '' : 's'} ready.'
                              ' Tap to compare and pick a favourite.'
                            : "We'll send these once the designer has them. "
                              "You'll be notified by email.",
                        actionLabel: p.selectedOptionId != null
                            ? 'Review your selection'
                            : 'Compare concepts',
                        actionIcon: Icons.view_carousel_outlined,
                        enabled: p.designOptionCount > 0,
                        onAction: _openConcepts,
                        complete: p.selectedOptionId != null,
                      ),
                      const SizedBox(height: 12),
                      _StepCard(
                        index: 3,
                        title: 'Approve the design',
                        subtitle: p.canApprove
                            ? 'When you approve, your selection moves to '
                              'production and you receive a quote.'
                            : p.state == 'approved' ||
                                    p.state == 'in_production' ||
                                    p.state == 'done'
                                ? 'Approved — production has started.'
                                : 'Pick a concept above first.',
                        actionLabel: 'Approve',
                        actionIcon: Icons.check_circle_outline,
                        enabled: p.canApprove,
                        onAction: _openApproval,
                        complete: p.state == 'approved' ||
                            p.state == 'in_production' ||
                            p.state == 'done',
                      ),
                      const SizedBox(height: 24),
                    ],
                  ),
                ),
    );
  }
}

class _Header extends StatelessWidget {
  final Project project;
  const _Header({required this.project});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    project.name.isEmpty ? project.code : project.name,
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w700,
                      color: SouthbrookColors.ink,
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: SouthbrookColors.stateChip(project.state)
                        .withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(999),
                  ),
                  child: Text(
                    project.stateLabel,
                    style: TextStyle(
                      color: SouthbrookColors.stateChip(project.state),
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              project.code,
              style: const TextStyle(
                fontSize: 12,
                color: SouthbrookColors.inkSoft,
              ),
            ),
            const SizedBox(height: 12),
            Wrap(
              spacing: 16,
              runSpacing: 6,
              children: [
                if (project.theme != null)
                  _Meta(icon: Icons.palette_outlined, text: project.theme!),
                if (project.dateTarget != null)
                  _Meta(icon: Icons.event,
                      text: 'Target ${project.dateTarget}'),
                if (project.dateCompleted != null)
                  _Meta(icon: Icons.flag_outlined,
                      text: 'Completed ${project.dateCompleted}'),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Meta extends StatelessWidget {
  final IconData icon;
  final String text;
  const _Meta({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: SouthbrookColors.inkSoft),
        const SizedBox(width: 4),
        Text(text, style: const TextStyle(
            fontSize: 12, color: SouthbrookColors.inkSoft)),
      ],
    );
  }
}

class _StepCard extends StatelessWidget {
  final int index;
  final String title;
  final String subtitle;
  final String actionLabel;
  final IconData actionIcon;
  final bool enabled;
  final bool complete;
  final VoidCallback onAction;

  const _StepCard({
    required this.index,
    required this.title,
    required this.subtitle,
    required this.actionLabel,
    required this.actionIcon,
    required this.enabled,
    required this.complete,
    required this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 28, height: 28,
                  decoration: BoxDecoration(
                    color: complete
                        ? SouthbrookColors.success
                        : SouthbrookColors.walnut,
                    shape: BoxShape.circle,
                  ),
                  child: Center(
                    child: complete
                        ? const Icon(Icons.check,
                            color: Colors.white, size: 16)
                        : Text(
                            '$index',
                            style: const TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    title,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: SouthbrookColors.ink,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.only(left: 40),
              child: Text(
                subtitle,
                style: const TextStyle(
                  fontSize: 13,
                  color: SouthbrookColors.inkSoft,
                  height: 1.4,
                ),
              ),
            ),
            const SizedBox(height: 14),
            Padding(
              padding: const EdgeInsets.only(left: 40),
              child: SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: enabled ? onAction : null,
                  icon: Icon(actionIcon, size: 18),
                  label: Text(actionLabel),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorPanel({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline,
                size: 48, color: SouthbrookColors.danger),
            const SizedBox(height: 16),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 14,
                color: SouthbrookColors.inkSoft,
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }
}
