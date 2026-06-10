// SPDX-License-Identifier: LGPL-3.0-only

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../theme.dart';

class ApprovalScreen extends StatefulWidget {
  final SouthbrookApiClient client;
  final int projectId;

  const ApprovalScreen({
    super.key,
    required this.client,
    required this.projectId,
  });

  @override
  State<ApprovalScreen> createState() => _ApprovalScreenState();
}

class _ApprovalScreenState extends State<ApprovalScreen> {
  final _notes = TextEditingController();
  bool _confirm = false;
  bool _busy = false;
  String? _error;
  bool _done = false;

  @override
  void dispose() {
    _notes.dispose();
    super.dispose();
  }

  Future<void> _approve() async {
    if (!_confirm) {
      setState(() => _error = 'Tick the box to confirm.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.client.approveProject(
        widget.projectId,
        notes: _notes.text.trim().isEmpty ? null : _notes.text.trim(),
        idempotencyKey: 'approve-${widget.projectId}',
      );
      if (!mounted) return;
      setState(() => _done = true);
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
      appBar: AppBar(title: const Text('Approve your design')),
      body: SafeArea(
        child: _done ? _DoneView(onClose: () => Navigator.of(context).pop(true))
                     : _Form(
                         notes: _notes,
                         confirm: _confirm,
                         busy: _busy,
                         error: _error,
                         onConfirmChanged: (v) =>
                             setState(() => _confirm = v ?? false),
                         onApprove: _approve,
                       ),
      ),
    );
  }
}

class _Form extends StatelessWidget {
  final TextEditingController notes;
  final bool confirm;
  final bool busy;
  final String? error;
  final ValueChanged<bool?> onConfirmChanged;
  final VoidCallback onApprove;

  const _Form({
    required this.notes,
    required this.confirm,
    required this.busy,
    required this.error,
    required this.onConfirmChanged,
    required this.onApprove,
  });

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Card(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.handshake_outlined,
                          color: SouthbrookColors.walnut),
                      SizedBox(width: 8),
                      Text(
                        "You're approving the design",
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w600,
                          color: SouthbrookColors.ink,
                        ),
                      ),
                    ],
                  ),
                  SizedBox(height: 12),
                  Text(
                    "Once you approve, we lock in the concept you picked and "
                    "send it to our shop. You'll receive a quote and a "
                    "production start date.",
                    style: TextStyle(
                      fontSize: 13,
                      color: SouthbrookColors.inkSoft,
                      height: 1.4,
                    ),
                  ),
                  SizedBox(height: 16),
                  _BulletList(items: [
                    'Your salesperson will confirm the quote.',
                    "You'll get an email when production starts.",
                    "Cancellation after this point goes through your "
                    "salesperson directly.",
                  ]),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: notes,
            minLines: 3,
            maxLines: 6,
            decoration: const InputDecoration(
              labelText: 'Notes for the designer (optional)',
              hintText: 'Anything we should know before we start?',
            ),
          ),
          const SizedBox(height: 16),
          CheckboxListTile(
            value: confirm,
            onChanged: onConfirmChanged,
            controlAffinity: ListTileControlAffinity.leading,
            contentPadding: EdgeInsets.zero,
            title: const Text(
              "I'm ready to approve and proceed to production.",
              style: TextStyle(fontSize: 14),
            ),
            activeColor: SouthbrookColors.walnut,
          ),
          if (error != null) ...[
            const SizedBox(height: 8),
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
                error!,
                style: const TextStyle(
                  color: SouthbrookColors.danger,
                  fontSize: 13,
                ),
              ),
            ),
          ],
          const SizedBox(height: 16),
          SizedBox(
            height: 52,
            child: ElevatedButton.icon(
              onPressed: busy ? null : onApprove,
              icon: busy
                  ? const SizedBox(
                      width: 16, height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.check_circle),
              label: Text(busy ? 'Approving…' : 'Approve and send to production'),
            ),
          ),
        ],
      ),
    );
  }
}

class _BulletList extends StatelessWidget {
  final List<String> items;
  const _BulletList({required this.items});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: items.map((item) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.only(top: 6, right: 8),
              child: Icon(Icons.fiber_manual_record,
                  size: 6, color: SouthbrookColors.inkSoft),
            ),
            Expanded(
              child: Text(
                item,
                style: const TextStyle(
                  fontSize: 13,
                  color: SouthbrookColors.inkSoft,
                  height: 1.4,
                ),
              ),
            ),
          ],
        ),
      )).toList(),
    );
  }
}

class _DoneView extends StatelessWidget {
  final VoidCallback onClose;
  const _DoneView({required this.onClose});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 88, height: 88,
              decoration: const BoxDecoration(
                color: SouthbrookColors.success,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.check, size: 56, color: Colors.white),
            ),
            const SizedBox(height: 24),
            const Text(
              'Approved!',
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w700,
                color: SouthbrookColors.ink,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              "Your kitchen is now in production. We'll email you when "
              "work begins and again when it's complete.",
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 14,
                color: SouthbrookColors.inkSoft,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 32),
            SizedBox(
              width: 200,
              height: 52,
              child: ElevatedButton(
                onPressed: onClose,
                child: const Text('Back to project'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
