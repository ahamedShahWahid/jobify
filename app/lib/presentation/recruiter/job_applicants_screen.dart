import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:jobify_app/core/error/exceptions.dart';
import 'package:jobify_app/core/format/date_formats.dart';
import 'package:jobify_app/data/jobs/applicant_of_job_dto.dart';
import 'package:jobify_app/data/jobs/application_stage.dart';
import 'package:jobify_app/data/jobs/recruiter_jobs_repository_impl.dart';
import 'package:jobify_app/presentation/applications/applications_screen.dart'
    show stageLabel;
import 'package:jobify_app/presentation/recruiter/recruiter_applicants_controller.dart';
import 'package:jobify_app/presentation/recruiter/resume_saver/resume_saver.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';
import 'package:jobify_app/presentation/widgets/jobify_score_badge.dart';

class JobApplicantsScreen extends ConsumerStatefulWidget {
  const JobApplicantsScreen({required this.jobId, super.key});

  final String jobId;

  @override
  ConsumerState<JobApplicantsScreen> createState() =>
      _JobApplicantsScreenState();
}

class _JobApplicantsScreenState extends ConsumerState<JobApplicantsScreen> {
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref
            .read(recruiterApplicantsControllerProvider(widget.jobId).notifier)
            .loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _download(String applicationId) async {
    final messenger = ScaffoldMessenger.of(context);
    if (!kIsWeb) {
      messenger.showSnackBar(
        const SnackBar(
          content: Text('Résumé download is available on the web app.'),
        ),
      );
      return;
    }
    messenger.showSnackBar(
      const SnackBar(content: Text('Downloading résumé…')),
    );
    try {
      final dl = await ref
          .read(recruiterJobsRepositoryProvider)
          .downloadResume(applicationId);
      saveResume(dl.bytes, dl.filename, dl.contentType);
    } on ApiException catch (e) {
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            e.statusCode == 404
                ? 'No résumé on file for this applicant.'
                : "Couldn't download the résumé. Try again.",
          ),
        ),
      );
    } on JobifyException {
      messenger.showSnackBar(
        const SnackBar(
          content: Text("Couldn't download the résumé. Try again."),
        ),
      );
    }
  }

  Future<void> _changeStage(
    String applicationId,
    ApplicationStage stage,
  ) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await ref
          .read(recruiterApplicantsControllerProvider(widget.jobId).notifier)
          .setStage(applicationId, stage);
    } catch (e) {
      final withdrew = e.toString().contains('application_withdrawn');
      messenger.showSnackBar(
        SnackBar(
          content: Text(
            withdrew ? 'Candidate withdrew' : "Couldn't update the stage",
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final value =
        ref.watch(recruiterApplicantsControllerProvider(widget.jobId));

    return Scaffold(
      appBar: AppBar(title: const Text('Applicants')),
      body: AsyncValueWidget<RecruiterApplicantsState>(
        value: value,
        onRetry: () => ref
            .read(recruiterApplicantsControllerProvider(widget.jobId).notifier)
            .refresh(),
        isEmpty: (s) => s.items.isEmpty,
        empty: () => const JobifyEmptyState(
          headline: 'No applicants yet',
          body: 'When candidates apply, they will show up here.',
          icon: Icons.people_outline,
        ),
        data: (s) => RefreshIndicator(
          onRefresh: () => ref
              .read(
                recruiterApplicantsControllerProvider(widget.jobId).notifier,
              )
              .refresh(),
          child: ListView.separated(
            controller: _scroll,
            padding: const EdgeInsets.all(JobifySpacing.lg),
            itemCount: s.items.length + 1,
            separatorBuilder: (_, __) =>
                const SizedBox(height: JobifySpacing.md),
            itemBuilder: (context, i) {
              if (i == s.items.length) {
                if (s.isLoadingMore) {
                  return const Padding(
                    padding: EdgeInsets.all(JobifySpacing.lg),
                    child: JobifyLoadingView(),
                  );
                }
                return const SizedBox.shrink();
              }
              return _ApplicantCard(
                applicant: s.items[i],
                onDownload: () => _download(s.items[i].applicationId),
                onChangeStage: (stage) =>
                    _changeStage(s.items[i].applicationId, stage),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _ApplicantCard extends StatelessWidget {
  const _ApplicantCard({
    required this.applicant,
    required this.onDownload,
    required this.onChangeStage,
  });

  final ApplicantOfJobDto applicant;
  final VoidCallback onDownload;
  final ValueChanged<ApplicationStage> onChangeStage;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final name = applicant.displayName ?? applicant.email ?? 'Applicant';
    final fit = applicant.matchExplanation?['fit'];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(JobifySpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(name, style: theme.textTheme.titleMedium),
                ),
                if (applicant.matchScore != null) ...[
                  const SizedBox(width: JobifySpacing.sm),
                  JobifyScoreBadge(score: applicant.matchScore!),
                ],
              ],
            ),
            const SizedBox(height: JobifySpacing.xs),
            Text(
              'Applied ${jobifyLongDateFormat.format(applicant.appliedAt)}',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            if (fit != null && fit.isNotEmpty) ...[
              const SizedBox(height: JobifySpacing.sm),
              Text(fit, style: theme.textTheme.bodyMedium),
            ],
            const SizedBox(height: JobifySpacing.sm),
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: JobifySpacing.sm,
              runSpacing: JobifySpacing.sm,
              children: [
                OutlinedButton.icon(
                  onPressed: onDownload,
                  icon: const Icon(Icons.download_outlined, size: 18),
                  label: const Text('Download résumé'),
                ),
                PopupMenuButton<ApplicationStage>(
                  tooltip: 'Change stage',
                  initialValue: applicant.stage,
                  onSelected: onChangeStage,
                  itemBuilder: (context) => const [
                    ApplicationStage.shortlisted,
                    ApplicationStage.interview,
                    ApplicationStage.offer,
                    ApplicationStage.hired,
                    ApplicationStage.rejected,
                  ]
                      .map(
                        (s) => PopupMenuItem(
                          value: s,
                          child: Text(stageLabel(s)),
                        ),
                      )
                      .toList(),
                  child: _StageChip(stage: applicant.stage),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _StageChip extends StatelessWidget {
  const _StageChip({required this.stage});

  final ApplicationStage stage;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: JobifySpacing.sm,
        vertical: JobifySpacing.xs,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            stageLabel(stage),
            style: theme.textTheme.labelSmall
                ?.copyWith(color: theme.colorScheme.onPrimaryContainer),
          ),
          const SizedBox(width: JobifySpacing.xs),
          Icon(
            Icons.arrow_drop_down,
            size: 16,
            color: theme.colorScheme.onPrimaryContainer,
          ),
        ],
      ),
    );
  }
}
