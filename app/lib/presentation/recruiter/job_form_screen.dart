import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:kpa_app/core/error/exceptions.dart';
import 'package:kpa_app/data/employers/employer_dto.dart';
import 'package:kpa_app/data/jobs/recruiter_job_dto.dart';
import 'package:kpa_app/presentation/recruiter/active_employer_provider.dart';
import 'package:kpa_app/presentation/recruiter/job_form_controller.dart';
import 'package:kpa_app/presentation/recruiter/recruiter_jobs_controller.dart';
import 'package:kpa_app/presentation/routing/routes.dart';
import 'package:kpa_app/presentation/theme/kpa_spacing.dart';
import 'package:kpa_app/presentation/widgets/async_value_widget.dart';
import 'package:kpa_app/presentation/widgets/kpa_empty_state.dart';
import 'package:kpa_app/presentation/widgets/kpa_loading_view.dart';

/// Edit-route entry. When navigated from the detail screen the full
/// [RecruiterJobDto] arrives via `extra`. On a deep link / refresh `extra` is
/// null, so resolve the job from the include-closed jobs list by id (mirrors
/// `RecruiterJobDetailScreen`) rather than silently rendering a blank CREATE
/// form against the wrong path.
class EditJobResolver extends ConsumerWidget {
  const EditJobResolver({required this.jobId, this.initialJob, super.key});

  final String jobId;
  final RecruiterJobDto? initialJob;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fromExtra = initialJob;
    if (fromExtra != null) return JobFormScreen(job: fromExtra);

    final value = ref.watch(recruiterJobsControllerProvider(true));
    return value.when(
      loading: () => const Scaffold(body: KpaLoadingView()),
      error: (_, __) => _notFound(context),
      data: (state) {
        for (final j in state.items) {
          if (j.id == jobId) return JobFormScreen(job: j);
        }
        return _notFound(context);
      },
    );
  }

  Widget _notFound(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Edit job')),
        body: KpaEmptyState(
          headline: 'Job not found',
          body: 'Open it from your jobs list to edit.',
          icon: Icons.search_off_outlined,
          primaryAction: FilledButton(
            onPressed: () => context.go(Routes.recruiterJobs),
            child: const Text('Back to my jobs'),
          ),
        ),
      );
}

/// Post-a-job (create) and edit-a-job form.
///
/// Create mode (`job == null`) needs an employer id, resolved from
/// [activeEmployerProvider] (falling back to the first employer of
/// [recruiterEmployersProvider]). Edit mode prefills from the passed
/// [RecruiterJobDto] and exposes the open/closed status toggle.
class JobFormScreen extends ConsumerStatefulWidget {
  const JobFormScreen({this.job, super.key});

  /// Non-null in edit mode (passed via `GoRouterState.extra`).
  final RecruiterJobDto? job;

  bool get isEdit => job != null;

  @override
  ConsumerState<JobFormScreen> createState() => _JobFormScreenState();
}

class _JobFormScreenState extends ConsumerState<JobFormScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _title;
  late final TextEditingController _description;
  late final TextEditingController _minExp;
  late final TextEditingController _maxExp;
  late final TextEditingController _ctcMin;
  late final TextEditingController _ctcMax;
  final _locationInput = TextEditingController();
  late List<String> _locations;
  late String _status;

  @override
  void initState() {
    super.initState();
    final j = widget.job;
    _title = TextEditingController(text: j?.title ?? '');
    _description = TextEditingController(text: j?.description ?? '');
    _minExp = TextEditingController(text: j?.minExpYears.toString() ?? '');
    _maxExp = TextEditingController(text: j?.maxExpYears.toString() ?? '');
    _ctcMin = TextEditingController(text: _ctcText(j?.ctcMin));
    _ctcMax = TextEditingController(text: _ctcText(j?.ctcMax));
    _locations = List<String>.from(j?.locations ?? const []);
    _status = j?.status ?? 'open';
  }

  static String _ctcText(double? v) {
    if (v == null) return '';
    return v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toString();
  }

  @override
  void dispose() {
    _title.dispose();
    _description.dispose();
    _minExp.dispose();
    _maxExp.dispose();
    _ctcMin.dispose();
    _ctcMax.dispose();
    _locationInput.dispose();
    super.dispose();
  }

  void _addLocation() {
    final v = _locationInput.text.trim();
    if (v.isEmpty || _locations.contains(v)) return;
    final messenger = ScaffoldMessenger.of(context);
    if (v.length > 100) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Location too long (max 100 chars).')),
      );
      return;
    }
    if (_locations.length >= 20) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Up to 20 locations.')),
      );
      return;
    }
    setState(() {
      _locations.add(v);
      _locationInput.clear();
    });
  }

  Future<void> _submit(String employerId) async {
    final messenger = ScaffoldMessenger.of(context);
    if (!_formKey.currentState!.validate()) return;
    if (_locations.isEmpty) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Add at least one location.')),
      );
      return;
    }

    final data = JobFormData(
      title: _title.text.trim(),
      description: _description.text.trim(),
      locations: _locations,
      minExpYears: int.parse(_minExp.text.trim()),
      maxExpYears: int.parse(_maxExp.text.trim()),
      ctcMin: double.tryParse(_ctcMin.text.trim()),
      ctcMax: double.tryParse(_ctcMax.text.trim()),
      status: _status,
    );

    final notifier = ref.read(jobFormControllerProvider.notifier);
    if (widget.isEdit) {
      await notifier.editJob(jobId: widget.job!.id, data: data);
    } else {
      await notifier.create(employerId: employerId, data: data);
    }
    if (!mounted) return;

    final state = ref.read(jobFormControllerProvider);
    if (state.hasError) {
      final e = state.error;
      final detail = e is ApiException ? e.detail : null;
      messenger.showSnackBar(
        SnackBar(
          content: Text(detail ?? "Couldn't save the job. Try again."),
        ),
      );
      return;
    }
    if (context.canPop()) context.pop();
  }

  @override
  Widget build(BuildContext context) {
    final saving = ref.watch(jobFormControllerProvider).isLoading;

    // Edit mode already has the employer id implicitly (the job belongs to it),
    // so no employer resolution is needed.
    if (widget.isEdit) {
      return _scaffold(
        saving: saving,
        employerId: widget.job!.id, // unused in edit path
        employerSelector: const SizedBox.shrink(),
      );
    }

    final employers = ref.watch(recruiterEmployersProvider);
    return AsyncValueWidget<List<EmployerDto>>(
      value: employers,
      onRetry: () => ref.invalidate(recruiterEmployersProvider),
      data: (list) {
        if (list.isEmpty) {
          return Scaffold(
            appBar: AppBar(title: const Text('Post a job')),
            body: const Center(
              child: Padding(
                padding: EdgeInsets.all(KpaSpacing.xl),
                child: Text('Create an employer before posting a job.'),
              ),
            ),
          );
        }
        final active = ref.watch(activeEmployerProvider) ?? list.first;
        return _scaffold(
          saving: saving,
          employerId: active.id,
          employerSelector: list.length > 1
              ? _EmployerDropdown(employers: list, active: active)
              : const SizedBox.shrink(),
        );
      },
    );
  }

  Widget _scaffold({
    required bool saving,
    required String employerId,
    required Widget employerSelector,
  }) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isEdit ? 'Edit job' : 'Post a job'),
        actions: [
          TextButton(
            onPressed: saving ? null : () => _submit(employerId),
            child: Text(saving ? 'Saving…' : 'Save'),
          ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(KpaSpacing.lg),
          children: [
            employerSelector,
            TextFormField(
              controller: _title,
              decoration: const InputDecoration(labelText: 'Title'),
              validator: (v) {
                final t = v?.trim() ?? '';
                if (t.length < 2) return 'At least 2 characters';
                if (t.length > 200) return 'Too long (max 200)';
                return null;
              },
            ),
            const SizedBox(height: KpaSpacing.md),
            TextFormField(
              controller: _description,
              minLines: 4,
              maxLines: 10,
              decoration: const InputDecoration(
                labelText: 'Description',
                alignLabelWithHint: true,
              ),
              validator: (v) {
                final t = v?.trim() ?? '';
                if (t.length < 10) return 'At least 10 characters';
                if (t.length > 10000) return 'Too long (max 10000)';
                return null;
              },
            ),
            const SizedBox(height: KpaSpacing.lg),
            Text('Locations', style: Theme.of(context).textTheme.labelLarge),
            Wrap(
              spacing: KpaSpacing.sm,
              children: [
                for (final loc in _locations)
                  Chip(
                    label: Text(loc),
                    onDeleted: () => setState(() => _locations.remove(loc)),
                  ),
              ],
            ),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _locationInput,
                    decoration:
                        const InputDecoration(labelText: 'Add location'),
                    onSubmitted: (_) => _addLocation(),
                  ),
                ),
                IconButton(
                  onPressed: _addLocation,
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
            const SizedBox(height: KpaSpacing.lg),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _minExp,
                    keyboardType: TextInputType.number,
                    decoration:
                        const InputDecoration(labelText: 'Min exp (yrs)'),
                    validator: _validateExp,
                  ),
                ),
                const SizedBox(width: KpaSpacing.md),
                Expanded(
                  child: TextFormField(
                    controller: _maxExp,
                    keyboardType: TextInputType.number,
                    decoration:
                        const InputDecoration(labelText: 'Max exp (yrs)'),
                    validator: (v) {
                      final base = _validateExp(v);
                      if (base != null) return base;
                      final min = int.tryParse(_minExp.text.trim());
                      final max = int.tryParse(v!.trim());
                      if (min != null && max != null && max < min) {
                        return 'Must be ≥ min';
                      }
                      return null;
                    },
                  ),
                ),
              ],
            ),
            const SizedBox(height: KpaSpacing.md),
            Row(
              children: [
                Expanded(
                  child: TextFormField(
                    controller: _ctcMin,
                    keyboardType: TextInputType.number,
                    decoration:
                        const InputDecoration(labelText: 'CTC min (₹/yr)'),
                    validator: _validateCtc,
                  ),
                ),
                const SizedBox(width: KpaSpacing.md),
                Expanded(
                  child: TextFormField(
                    controller: _ctcMax,
                    keyboardType: TextInputType.number,
                    decoration:
                        const InputDecoration(labelText: 'CTC max (₹/yr)'),
                    validator: (v) {
                      final base = _validateCtc(v);
                      if (base != null) return base;
                      final min = double.tryParse(_ctcMin.text.trim());
                      final max = double.tryParse(v?.trim() ?? '');
                      if (min != null && max != null && max < min) {
                        return 'Must be ≥ CTC min';
                      }
                      return null;
                    },
                  ),
                ),
              ],
            ),
            if (widget.isEdit) ...[
              const SizedBox(height: KpaSpacing.lg),
              Text('Status', style: Theme.of(context).textTheme.labelLarge),
              const SizedBox(height: KpaSpacing.sm),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'open', label: Text('Open')),
                  ButtonSegment(value: 'closed', label: Text('Closed')),
                ],
                selected: {_status},
                onSelectionChanged: (s) => setState(() => _status = s.first),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String? _validateExp(String? v) {
    final t = v?.trim() ?? '';
    if (t.isEmpty) return 'Required';
    final n = int.tryParse(t);
    if (n == null) return 'Whole number';
    if (n < 0 || n > 50) return '0–50';
    return null;
  }

  String? _validateCtc(String? v) {
    final t = v?.trim() ?? '';
    if (t.isEmpty) return null; // optional
    final n = double.tryParse(t);
    if (n == null) return 'Enter a number';
    if (n < 0) return 'Must be ≥ 0';
    return null;
  }
}

class _EmployerDropdown extends ConsumerWidget {
  const _EmployerDropdown({required this.employers, required this.active});

  final List<EmployerDto> employers;
  final EmployerDto active;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.only(bottom: KpaSpacing.md),
      child: DropdownButtonFormField<String>(
        initialValue: active.id,
        decoration: const InputDecoration(labelText: 'Company'),
        items: [
          for (final e in employers)
            DropdownMenuItem(value: e.id, child: Text(e.name)),
        ],
        onChanged: (id) {
          if (id == null) return;
          final selected = employers.firstWhere((e) => e.id == id);
          ref.read(activeEmployerProvider.notifier).select(selected);
        },
      ),
    );
  }
}
