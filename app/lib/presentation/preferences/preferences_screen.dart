import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_dto.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/data/resume/resume_dto.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class PreferencesScreen extends ConsumerStatefulWidget {
  const PreferencesScreen({super.key, this.resume});

  final ResumeDto? resume;

  @override
  ConsumerState<PreferencesScreen> createState() => _PreferencesScreenState();
}

class _PreferencesScreenState extends ConsumerState<PreferencesScreen> {
  final _formKey = GlobalKey<FormState>();
  final _locationInput = TextEditingController();
  late final TextEditingController _expectedCtc;
  List<String> _locations = [];
  DesiredRole? _desiredRole;
  bool _seeded = false;

  @override
  void initState() {
    super.initState();
    _expectedCtc = TextEditingController();
  }

  void _seedFromPreferences(PreferencesDto prefs) {
    if (_seeded) return;
    _seeded = true;
    // Keep the raw seeded value INCLUDING `unknown`: an untouched unknown
    // is omitted on save, preserving the server's role instead of clearing.
    _desiredRole = prefs.desiredRole;
    _locations = List<String>.from(prefs.locations);
    _expectedCtc.text = prefs.expectedCtc ?? '';
  }

  @override
  void dispose() {
    _locationInput.dispose();
    _expectedCtc.dispose();
    super.dispose();
  }

  void _addLocation() {
    final v = _locationInput.text.trim();
    if (v.isEmpty ||
        _locations.contains(v) ||
        v.length > 100 ||
        _locations.length >= 10) {
      return;
    }
    setState(() {
      _locations.add(v);
      _locationInput.clear();
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final update = PreferencesUpdateDto(
      desiredRole: _desiredRole,
      locations: _locations,
      expectedCtc: num.tryParse(_expectedCtc.text.trim()),
    );
    final ok =
        await ref.read(preferencesControllerProvider.notifier).submit(update);
    if (!mounted) return;
    if (ok) {
      if (context.canPop()) context.pop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't save. Try again.")),
      );
    }
  }

  void _skip() {
    if (context.canPop()) context.pop();
  }

  @override
  Widget build(BuildContext context) {
    final prefsState = ref.watch(preferencesControllerProvider);
    if (prefsState.hasValue) _seedFromPreferences(prefsState.requireValue);
    final saving = prefsState.isLoading && _seeded;

    // The form must only render once seeded from real data — saving a
    // half-seeded form would clear server-side values. Skip stays available
    // in every state (this is a capture flow the user may bail out of).
    if (!_seeded) {
      return Scaffold(
        appBar: AppBar(
          title: const Text('What are you looking for?'),
          actions: [
            TextButton(onPressed: _skip, child: const Text('Skip')),
          ],
        ),
        body: Center(
          child: prefsState.hasError
              ? Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text("Couldn't load your preferences."),
                    const SizedBox(height: JobifySpacing.sm),
                    TextButton(
                      onPressed: () =>
                          ref.invalidate(preferencesControllerProvider),
                      child: const Text('Retry'),
                    ),
                  ],
                )
              : const CircularProgressIndicator(),
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: const Text('What are you looking for?'),
        actions: [
          TextButton(onPressed: _skip, child: const Text('Skip')),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          children: [
            _ResumeSummaryCard(resume: widget.resume),
            const SizedBox(height: JobifySpacing.xl),
            DropdownButtonFormField<DesiredRole>(
              // `unknown` (unrecognised server value) has no menu item;
              // show it as no selection. `_desiredRole` keeps the raw
              // `unknown` until the user picks something, so an untouched
              // save omits the key and preserves the server value.
              initialValue:
                  _desiredRole == DesiredRole.unknown ? null : _desiredRole,
              decoration: const InputDecoration(labelText: 'Desired role'),
              items: [
                // A null item so a previously set role can be CLEARED.
                const DropdownMenuItem<DesiredRole>(
                  child: Text('No preference'),
                ),
                for (final role in DesiredRole.values
                    .where((r) => r != DesiredRole.unknown))
                  DropdownMenuItem(value: role, child: Text(role.label)),
              ],
              onChanged: (role) => setState(() => _desiredRole = role),
            ),
            const SizedBox(height: JobifySpacing.lg),
            Text('Locations', style: Theme.of(context).textTheme.labelLarge),
            Wrap(
              spacing: JobifySpacing.sm,
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
            const SizedBox(height: JobifySpacing.lg),
            TextFormField(
              controller: _expectedCtc,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Expected CTC (₹/yr)'),
            ),
            const SizedBox(height: JobifySpacing.xl),
            FilledButton(
              onPressed: saving ? null : _save,
              child: Text(saving ? 'Saving…' : 'Save'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResumeSummaryCard extends StatelessWidget {
  const _ResumeSummaryCard({required this.resume});
  final ResumeDto? resume;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final parsed = resume?.parsedJson;
    if (resume == null) return const SizedBox.shrink();
    if (parsed == null) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          child: Text(
            "We couldn't read your résumé — tell us directly below.",
            style: theme.textTheme.bodyMedium,
          ),
        ),
      );
    }
    final name = parsed['name'] as String?;
    final skills = (parsed['skills'] as List?)?.cast<String>() ?? const [];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(JobifySpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Your résumé', style: theme.textTheme.titleMedium),
            const SizedBox(height: JobifySpacing.xs),
            if (name != null) Text(name, style: theme.textTheme.bodyMedium),
            if (skills.isNotEmpty) ...[
              const SizedBox(height: JobifySpacing.sm),
              Wrap(
                spacing: JobifySpacing.sm,
                children: [
                  for (final s in skills.take(10)) Chip(label: Text(s)),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
