// SPDX-License-Identifier: LGPL-3.0-only

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../models/concept.dart';
import '../theme.dart';
import 'approval_screen.dart';

class ConceptReviewScreen extends StatefulWidget {
  final SouthbrookApiClient client;
  final int projectId;
  final int? currentlySelectedId;

  const ConceptReviewScreen({
    super.key,
    required this.client,
    required this.projectId,
    this.currentlySelectedId,
  });

  @override
  State<ConceptReviewScreen> createState() => _ConceptReviewScreenState();
}

class _ConceptReviewScreenState extends State<ConceptReviewScreen> {
  late Future<List<Concept>> _conceptsFuture;
  int? _localSelectedId;
  bool _selecting = false;
  String? _selectError;

  @override
  void initState() {
    super.initState();
    _localSelectedId = widget.currentlySelectedId;
    _conceptsFuture = _fetch();
  }

  Future<List<Concept>> _fetch() async {
    final raw = await widget.client.listConcepts(widget.projectId);
    final list = raw
        .map((j) => Concept.fromJson(j as Map<String, dynamic>))
        .toList();
    final preSelected = list.where((c) => c.isSelected).firstOrNull;
    if (preSelected != null) _localSelectedId = preSelected.id;
    return list;
  }

  Future<void> _refresh() async {
    setState(() {
      _conceptsFuture = _fetch();
    });
    await _conceptsFuture;
  }

  Future<void> _select(int optionId) async {
    if (_selecting) return;
    setState(() {
      _selecting = true;
      _selectError = null;
    });
    try {
      await widget.client.selectConcept(
        widget.projectId, optionId,
        idempotencyKey: 'select-${widget.projectId}-$optionId',
      );
      if (!mounted) return;
      setState(() => _localSelectedId = optionId);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
        content: Text('Concept selected. You can change it any time before '
            'you approve.'),
      ));
    } on ApiException catch (e) {
      setState(() => _selectError = e.message.isNotEmpty ? e.message : e.code);
    } catch (e) {
      setState(() => _selectError = '$e');
    } finally {
      if (mounted) setState(() => _selecting = false);
    }
  }

  Future<void> _proceedToApproval() async {
    final changed = await Navigator.of(context).push<bool>(MaterialPageRoute(
      builder: (_) => ApprovalScreen(
        client: widget.client,
        projectId: widget.projectId,
      ),
    ));
    if (changed == true && mounted) Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Choose your favourite')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<Concept>>(
          future: _conceptsFuture,
          builder: (context, snap) {
            if (snap.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return ListView(children: [
                const SizedBox(height: 80),
                const Icon(Icons.cloud_off,
                    size: 48, color: SouthbrookColors.inkSoft),
                const SizedBox(height: 12),
                Center(
                  child: Text(
                    '${snap.error}',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        color: SouthbrookColors.inkSoft, fontSize: 13),
                  ),
                ),
              ]);
            }
            final concepts = snap.data ?? const <Concept>[];
            if (concepts.isEmpty) {
              return ListView(children: const [
                SizedBox(height: 80),
                Icon(Icons.view_carousel_outlined,
                    size: 64, color: SouthbrookColors.divider),
                SizedBox(height: 16),
                Center(
                  child: Text(
                    'No concepts yet',
                    style: TextStyle(
                      fontSize: 18,
                      color: SouthbrookColors.inkSoft,
                    ),
                  ),
                ),
              ]);
            }
            return Column(
              children: [
                Expanded(
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: concepts.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (context, i) {
                      final c = concepts[i];
                      final isSelected = _localSelectedId == c.id;
                      return _ConceptCard(
                        concept: c,
                        index: i,
                        isSelected: isSelected,
                        busy: _selecting,
                        onSelect: () => _select(c.id),
                      );
                    },
                  ),
                ),
                if (_selectError != null)
                  Container(
                    width: double.infinity,
                    margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: SouthbrookColors.danger.withValues(alpha: 0.08),
                      border: Border.all(
                        color: SouthbrookColors.danger.withValues(alpha: 0.3),
                      ),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      _selectError!,
                      style: const TextStyle(
                        color: SouthbrookColors.danger,
                        fontSize: 13,
                      ),
                    ),
                  ),
                if (_localSelectedId != null)
                  SafeArea(
                    top: false,
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      child: SizedBox(
                        width: double.infinity,
                        height: 52,
                        child: ElevatedButton.icon(
                          onPressed: _selecting ? null : _proceedToApproval,
                          icon: const Icon(Icons.check_circle_outline),
                          label: const Text('Approve this design'),
                        ),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _ConceptCard extends StatelessWidget {
  final Concept concept;
  final int index;
  final bool isSelected;
  final bool busy;
  final VoidCallback onSelect;

  const _ConceptCard({
    required this.concept,
    required this.index,
    required this.isSelected,
    required this.busy,
    required this.onSelect,
  });

  String get _letter => String.fromCharCode(65 + (index % 26)); // A, B, C…

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(
          color: isSelected
              ? SouthbrookColors.walnut
              : SouthbrookColors.divider,
          width: isSelected ? 2.5 : 1,
        ),
      ),
      child: InkWell(
        onTap: busy ? null : onSelect,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 36, height: 36,
                    decoration: BoxDecoration(
                      color: isSelected
                          ? SouthbrookColors.walnut
                          : SouthbrookColors.linen,
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        _letter,
                        style: TextStyle(
                          color: isSelected
                              ? Colors.white
                              : SouthbrookColors.walnut,
                          fontWeight: FontWeight.w700,
                          fontSize: 16,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      concept.name.isEmpty
                          ? 'Concept $_letter'
                          : concept.name,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: SouthbrookColors.ink,
                      ),
                    ),
                  ),
                  if (isSelected)
                    const Icon(Icons.check_circle,
                        color: SouthbrookColors.walnut),
                ],
              ),
              if (concept.thumbnailUrl != null) ...[
                const SizedBox(height: 12),
                AspectRatio(
                  aspectRatio: 4 / 3,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: Image.network(
                      concept.thumbnailUrl!,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => _Placeholder(letter: _letter),
                      loadingBuilder: (context, child, progress) =>
                          progress == null
                              ? child
                              : Container(
                                  color: SouthbrookColors.linen,
                                  child: const Center(
                                    child: CircularProgressIndicator(),
                                  ),
                                ),
                    ),
                  ),
                ),
              ] else ...[
                const SizedBox(height: 12),
                AspectRatio(
                  aspectRatio: 4 / 3,
                  child: _Placeholder(letter: _letter),
                ),
              ],
              if (concept.description != null &&
                  concept.description!.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  concept.description!,
                  style: const TextStyle(
                    fontSize: 13,
                    color: SouthbrookColors.inkSoft,
                    height: 1.4,
                  ),
                ),
              ],
              if (concept.estimatedPrice != null) ...[
                const SizedBox(height: 12),
                Row(
                  children: [
                    const Icon(Icons.attach_money,
                        size: 16, color: SouthbrookColors.inkSoft),
                    Text(
                      'Estimated: \$${concept.estimatedPrice!.toStringAsFixed(0)}',
                      style: const TextStyle(
                        fontSize: 13,
                        color: SouthbrookColors.inkSoft,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ],
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: isSelected
                    ? const _SelectedBadge()
                    : OutlinedButton(
                        onPressed: busy ? null : onSelect,
                        child: const Text('Pick this concept'),
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SelectedBadge extends StatelessWidget {
  const _SelectedBadge();
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: BoxDecoration(
        color: SouthbrookColors.walnut.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(6),
      ),
      child: const Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.check_circle, color: SouthbrookColors.walnut, size: 18),
          SizedBox(width: 8),
          Text(
            'Your favourite',
            style: TextStyle(
              color: SouthbrookColors.walnut,
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }
}

class _Placeholder extends StatelessWidget {
  final String letter;
  const _Placeholder({required this.letter});
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: SouthbrookColors.linen,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Center(
        child: Text(
          'Concept $letter',
          style: const TextStyle(
            color: SouthbrookColors.walnutLight,
            fontSize: 18,
            fontWeight: FontWeight.w600,
          ),
        ),
      ),
    );
  }
}

extension<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
