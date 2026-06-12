import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/presentation/recruiter/recruiter_job_card.dart';
import 'package:jobify_app/presentation/recruiter/recruiter_jobs_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';
import 'package:jobify_app/presentation/widgets/async_value_widget.dart';
import 'package:jobify_app/presentation/widgets/jobify_empty_state.dart';
import 'package:jobify_app/presentation/widgets/jobify_loading_view.dart';

class RecruiterJobsScreen extends ConsumerStatefulWidget {
  const RecruiterJobsScreen({super.key});

  @override
  ConsumerState<RecruiterJobsScreen> createState() =>
      _RecruiterJobsScreenState();
}

class _RecruiterJobsScreenState extends ConsumerState<RecruiterJobsScreen> {
  bool _includeClosed = false;
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 200) {
        ref
            .read(recruiterJobsControllerProvider(_includeClosed).notifier)
            .loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final value = ref.watch(recruiterJobsControllerProvider(_includeClosed));

    return Scaffold(
      appBar: AppBar(
        title: const Text('My jobs'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'Post a job',
            onPressed: () => context.go('/recruiter/jobs/new'),
          ),
        ],
      ),
      body: Column(
        children: [
          SwitchListTile(
            value: _includeClosed,
            onChanged: (v) => setState(() => _includeClosed = v),
            title: const Text('Show closed'),
            dense: true,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: JobifySpacing.lg),
          ),
          Expanded(
            child: AsyncValueWidget<RecruiterJobsState>(
              value: value,
              onRetry: () => ref
                  .read(
                    recruiterJobsControllerProvider(_includeClosed).notifier,
                  )
                  .refresh(),
              isEmpty: (s) => s.items.isEmpty,
              empty: () => JobifyEmptyState(
                headline: 'No jobs yet',
                body: 'Post your first role to start receiving applicants.',
                icon: Icons.work_outline,
                primaryAction: FilledButton(
                  onPressed: () => context.go('/recruiter/jobs/new'),
                  child: const Text('Post your first role'),
                ),
              ),
              data: (s) => RefreshIndicator(
                onRefresh: () => ref
                    .read(
                      recruiterJobsControllerProvider(_includeClosed).notifier,
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
                    final job = s.items[i];
                    return RecruiterJobCard(
                      job: job,
                      onTap: () => context.go(
                        '/recruiter/jobs/${job.id}',
                        extra: job,
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
