import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/resume/resume_dto.dart';
import 'package:kpa_app/data/resume/resume_parse_status.dart';
import 'package:kpa_app/presentation/resume/resume_controller.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';

final _dateFormat = DateFormat.yMMMMd();

const _extToContentType = <String, String>{
  'pdf': 'application/pdf',
  'doc': 'application/msword',
  'docx':
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};

class ResumeScreen extends ConsumerStatefulWidget {
  const ResumeScreen({super.key});

  @override
  ConsumerState<ResumeScreen> createState() => _ResumeScreenState();
}

class _ResumeScreenState extends ConsumerState<ResumeScreen> {
  Future<void> _pickAndUpload() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: const ['pdf', 'doc', 'docx'],
      withData: true,
    );
    if (result == null || result.files.isEmpty) return; // cancelled
    final file = result.files.single;
    final bytes = file.bytes;
    final ext = (file.extension ?? '').toLowerCase();
    final contentType = _extToContentType[ext];
    if (bytes == null || contentType == null) {
      _snack('Unsupported file type (PDF, DOC, DOCX).');
      return;
    }
    final ok =
        await ref.read(resumeControllerProvider.notifier).uploadFromPicked(
              bytes: bytes,
              filename: file.name,
              contentType: contentType,
            );
    if (!mounted) return;
    if (ok) {
      Future.delayed(const Duration(seconds: 2), _refreshIfMounted);
      Future.delayed(const Duration(seconds: 5), _refreshIfMounted);
    } else {
      _snack(_errorText(ref.read(resumeControllerProvider).error));
    }
  }

  void _refreshIfMounted() {
    if (mounted) ref.read(resumeControllerProvider.notifier).refresh();
  }

  void _snack(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  String _errorText(Object? e) {
    if (e is ApiException && e.statusCode == 415) {
      return 'Unsupported file type (PDF, DOC, DOCX).';
    }
    if (e is ApiException && e.statusCode == 413) {
      return 'File too large (max 10 MB).';
    }
    if (e is NetworkException) return "Couldn't reach KPA.";
    return "Couldn't upload. Try again.";
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(resumeControllerProvider);
    final uploading = state.isLoading;
    return Scaffold(
      appBar: AppBar(title: const Text('Résumé')),
      body: RefreshIndicator(
        onRefresh: () => ref.read(resumeControllerProvider.notifier).refresh(),
        child: ListView(
          padding: const EdgeInsets.all(KpaSpacing.lg),
          children: [
            AsyncValueWidget<ResumeDto?>(
              value: state,
              onRetry: () =>
                  ref.read(resumeControllerProvider.notifier).refresh(),
              data: (resume) =>
                  resume == null ? const _Empty() : _ResumeCard(resume: resume),
            ),
            const SizedBox(height: KpaSpacing.xl),
            FilledButton.icon(
              onPressed: uploading ? null : _pickAndUpload,
              icon: const Icon(Icons.upload_file),
              label: Text(
                  uploading ? 'Uploading…' : 'Upload / Replace r\xe9sum\xe9'),
            ),
          ],
        ),
      ),
    );
  }
}

class _Empty extends StatelessWidget {
  const _Empty();

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: KpaSpacing.xl),
        child: Text(
          'No r\xe9sum\xe9 yet. Upload one so we can match you to roles.',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
      );
}

class _ResumeCard extends StatelessWidget {
  const _ResumeCard({required this.resume});

  final ResumeDto resume;

  ({String label, Color fg, Color bg}) _status(BuildContext context) {
    final c = Theme.of(context).colorScheme;
    switch (resume.parseStatus) {
      case ResumeParseStatus.parsed:
        return (
          label: 'Ready',
          fg: c.onPrimaryContainer,
          bg: c.primaryContainer,
        );
      case ResumeParseStatus.failed:
        return (
          label: "Couldn't parse — try again",
          fg: c.onErrorContainer,
          bg: c.errorContainer,
        );
      case ResumeParseStatus.pending:
      case ResumeParseStatus.parsing:
      case ResumeParseStatus.unknown:
        return (
          label: 'Processing…',
          fg: c.onSurfaceVariant,
          bg: c.surfaceContainerHighest,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final s = _status(context);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(KpaSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(resume.originalFilename, style: theme.textTheme.titleMedium),
            const SizedBox(height: KpaSpacing.xs),
            Text(
              'Uploaded ${_dateFormat.format(resume.createdAt)}',
              style: theme.textTheme.bodySmall
                  ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
            ),
            const SizedBox(height: KpaSpacing.sm),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: KpaSpacing.sm,
                vertical: KpaSpacing.xs,
              ),
              decoration: BoxDecoration(
                color: s.bg,
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                s.label,
                style: theme.textTheme.labelSmall?.copyWith(color: s.fg),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
