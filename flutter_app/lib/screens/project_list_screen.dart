// SPDX-License-Identifier: LGPL-3.0-only

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models/project.dart';
import '../services/auth_storage.dart';
import '../theme.dart';
import 'login_screen.dart';
import 'project_detail_screen.dart';

class ProjectListScreen extends StatefulWidget {
  final SouthbrookApiClient client;
  final AuthStorage storage;

  const ProjectListScreen({
    super.key,
    required this.client,
    required this.storage,
  });

  @override
  State<ProjectListScreen> createState() => _ProjectListScreenState();
}

class _ProjectListScreenState extends State<ProjectListScreen> {
  late Future<List<Project>> _projectsFuture;

  @override
  void initState() {
    super.initState();
    _projectsFuture = _fetch();
  }

  Future<List<Project>> _fetch() async {
    final raw = await widget.client.listProjects();
    return raw
        .map((j) => Project.fromJson(j as Map<String, dynamic>))
        .toList();
  }

  Future<void> _refresh() async {
    setState(() {
      _projectsFuture = _fetch();
    });
    await _projectsFuture;
  }

  Future<void> _signOut() async {
    await widget.storage.clear();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(
      builder: (_) => LoginScreen(storage: widget.storage),
    ));
  }

  String _friendlyError(Object? error) {
    if (error is ApiException) {
      // 5xx (incl. the retryable 502 from the origin) — distinct from a real
      // client/data error.
      if (error.statusCode >= 500) {
        return 'Our server is temporarily unavailable. '
            'Please try again in a moment.';
      }
      return error.message.isNotEmpty ? error.message : error.code;
    }
    return "We couldn't reach the server. "
        'Check your connection and try again.';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Your kitchen projects'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            tooltip: 'Sign out',
            onPressed: _signOut,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<Project>>(
          future: _projectsFuture,
          builder: (context, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              final error = snap.error;
              if (error is ApiException && error.statusCode == 401) {
                // SessionGuard (wired via client.onUnauthorized) is already
                // routing back to login — just hold a spinner until it does.
                return const Center(child: CircularProgressIndicator());
              }
              return _ErrorState(
                message: _friendlyError(error),
                onRetry: _refresh,
              );
            }
            final projects = snap.data ?? const <Project>[];
            if (projects.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 80),
                  Icon(Icons.kitchen, size: 64, color: SouthbrookColors.divider),
                  SizedBox(height: 16),
                  Text(
                    'No projects yet',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: 18,
                      color: SouthbrookColors.inkSoft,
                    ),
                  ),
                  SizedBox(height: 8),
                  Padding(
                    padding: EdgeInsets.symmetric(horizontal: 48),
                    child: Text(
                      "Your salesperson will create a project for you. "
                      "Once it's here you'll be able to upload a photo of "
                      "your kitchen and review the concepts we design.",
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 14,
                        color: SouthbrookColors.inkSoft,
                      ),
                    ),
                  ),
                ],
              );
            }
            return ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: projects.length,
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemBuilder: (context, i) => _ProjectCard(
                project: projects[i],
                onTap: () async {
                  await Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => ProjectDetailScreen(
                      client: widget.client,
                      storage: widget.storage,
                      projectId: projects[i].id,
                    ),
                  ));
                  _refresh();
                },
              ),
            );
          },
        ),
      ),
    );
  }
}

class _ProjectCard extends StatelessWidget {
  final Project project;
  final VoidCallback onTap;
  const _ProjectCard({required this.project, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
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
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: SouthbrookColors.ink,
                      ),
                    ),
                  ),
                  _StatePill(state: project.state, label: project.stateLabel),
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
              if (project.theme != null) ...[
                const SizedBox(height: 8),
                Row(
                  children: [
                    const Icon(Icons.palette_outlined,
                        size: 14, color: SouthbrookColors.inkSoft),
                    const SizedBox(width: 4),
                    Text(
                      project.theme!,
                      style: const TextStyle(
                        fontSize: 12,
                        color: SouthbrookColors.inkSoft,
                      ),
                    ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatePill extends StatelessWidget {
  final String state;
  final String label;
  const _StatePill({required this.state, required this.label});

  @override
  Widget build(BuildContext context) {
    final color = SouthbrookColors.stateChip(state);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: color,
          fontSize: 11,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;
  const _ErrorState({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off, size: 48, color: SouthbrookColors.inkSoft),
            const SizedBox(height: 16),
            const Text(
              "Couldn't load projects",
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 13,
                color: SouthbrookColors.inkSoft,
              ),
            ),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}
