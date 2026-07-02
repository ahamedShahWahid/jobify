import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:jobify_app/data/me/profile_update_dto.dart';
import 'package:jobify_app/data/preferences/desired_role.dart';
import 'package:jobify_app/data/preferences/preferences_update_dto.dart';
import 'package:jobify_app/presentation/preferences/preferences_controller.dart';
import 'package:jobify_app/presentation/profile/me_controller.dart';
import 'package:jobify_app/presentation/profile/profile_edit_controller.dart';
import 'package:jobify_app/presentation/theme/jobify_spacing.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});
  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _fullName;
  late final TextEditingController _experience;
  late final TextEditingController _notice;
  late final TextEditingController _currentCtc;
  late final TextEditingController _expectedCtc;
  final _locationInput = TextEditingController();
  late List<String> _locations;
  DesiredRole? _desiredRole;

  @override
  void initState() {
    super.initState();
    final a = ref.read(meControllerProvider).value?.applicant;
    final prefs = ref.read(preferencesControllerProvider).value;
    _fullName = TextEditingController(text: a?.fullName ?? '');
    _experience = TextEditingController(text: a?.yearsExperience ?? '');
    _notice =
        TextEditingController(text: a?.noticePeriodDays?.toString() ?? '');
    _currentCtc = TextEditingController(text: a?.currentCtc ?? '');
    _expectedCtc = TextEditingController(text: prefs?.expectedCtc ?? '');
    _locations = List<String>.from(prefs?.locations ?? const []);
    _desiredRole = prefs?.desiredRole;
  }

  @override
  void dispose() {
    _fullName.dispose();
    _experience.dispose();
    _notice.dispose();
    _currentCtc.dispose();
    _expectedCtc.dispose();
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
    if (_locations.length >= 10) {
      messenger.showSnackBar(
        const SnackBar(content: Text('Up to 10 locations.')),
      );
      return;
    }
    setState(() {
      _locations.add(v);
      _locationInput.clear();
    });
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final profileUpdate = ProfileUpdateDto(
      fullName: _fullName.text.trim(),
      noticePeriodDays: int.tryParse(_notice.text.trim()),
      currentCtc: num.tryParse(_currentCtc.text.trim()),
      yearsExperience: num.tryParse(_experience.text.trim()),
    );
    final preferencesUpdate = PreferencesUpdateDto(
      desiredRole: _desiredRole,
      locations: _locations,
      expectedCtc: num.tryParse(_expectedCtc.text.trim()),
    );
    final profileOk = await ref
        .read(profileEditControllerProvider.notifier)
        .submit(profileUpdate);
    final prefsOk = await ref
        .read(preferencesControllerProvider.notifier)
        .submit(preferencesUpdate);
    if (!mounted) return;
    if (profileOk && prefsOk) {
      if (context.canPop()) context.pop();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Couldn't save. Try again.")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final saving = ref.watch(profileEditControllerProvider).isLoading ||
        ref.watch(preferencesControllerProvider).isLoading;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Edit Profile'),
        actions: [
          TextButton(
            onPressed: saving ? null : _save,
            child: Text(saving ? 'Saving…' : 'Save'),
          ),
        ],
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(JobifySpacing.lg),
          children: [
            TextFormField(
              controller: _fullName,
              decoration: const InputDecoration(labelText: 'Full name'),
              validator: (v) {
                final t = v?.trim() ?? '';
                if (t.isEmpty) return 'Required';
                if (t.length > 200) return 'Too long (max 200)';
                return null;
              },
            ),
            const SizedBox(height: JobifySpacing.lg),
            DropdownButtonFormField<DesiredRole>(
              initialValue: _desiredRole,
              decoration: const InputDecoration(labelText: 'Desired role'),
              items: [
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
              controller: _experience,
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              decoration:
                  const InputDecoration(labelText: 'Years of experience'),
              validator: (v) =>
                  _validateOptionalNumber(v, min: 0, max: 60, maxDecimals: 1),
            ),
            TextFormField(
              controller: _notice,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Notice period (days)'),
              validator: (v) =>
                  _validateOptionalNumber(v, min: 0, max: 365, maxDecimals: 0),
            ),
            TextFormField(
              controller: _currentCtc,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Current CTC (₹/yr)'),
              validator: (v) => _validateOptionalNumber(
                v,
                min: 0,
                max: 9999999999.99,
                maxDecimals: 2,
              ),
            ),
            TextFormField(
              controller: _expectedCtc,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Expected CTC (₹/yr)'),
              validator: (v) => _validateOptionalNumber(
                v,
                min: 0,
                max: 9999999999.99,
                maxDecimals: 2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Validate an optional numeric form field against the backend's bounds.
/// Empty is allowed (the field clears). Returns an error message, or null when
/// valid. `maxDecimals` mirrors the column scale (e.g. Numeric(4,1) → 1) so the
/// user is told instead of the DB silently rounding.
String? _validateOptionalNumber(
  String? raw, {
  required num min,
  required num max,
  required int maxDecimals,
}) {
  final t = raw?.trim() ?? '';
  if (t.isEmpty) return null;
  final n = num.tryParse(t);
  if (n == null) return 'Enter a number';
  if (n < min || n > max) return 'Must be between $min and $max';
  final dot = t.indexOf('.');
  if (dot >= 0 && t.length - dot - 1 > maxDecimals) {
    return maxDecimals == 0
        ? 'Whole number only'
        : 'At most $maxDecimals decimal place${maxDecimals == 1 ? '' : 's'}';
  }
  return null;
}
