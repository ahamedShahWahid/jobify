// GENERATED CODE - DO NOT MODIFY BY HAND
// coverage:ignore-file
// ignore_for_file: type=lint
// ignore_for_file: unused_element, deprecated_member_use, deprecated_member_use_from_same_package, use_function_type_syntax_for_parameters, unnecessary_const, avoid_init_to_null, invalid_override_different_default_values_named, prefer_expression_function_bodies, annotate_overrides, invalid_annotation_target, unnecessary_question_mark

part of 'auth_dto.dart';

// **************************************************************************
// FreezedGenerator
// **************************************************************************

// dart format off
T _$identity<T>(T value) => value;

/// @nodoc
mixin _$SignInResponseDto {
  String get access;
  String get refresh;
  AuthUserDto get user;
  AuthApplicantDto? get applicant;

  /// Create a copy of SignInResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $SignInResponseDtoCopyWith<SignInResponseDto> get copyWith =>
      _$SignInResponseDtoCopyWithImpl<SignInResponseDto>(
          this as SignInResponseDto, _$identity);

  /// Serializes this SignInResponseDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is SignInResponseDto &&
            (identical(other.access, access) || other.access == access) &&
            (identical(other.refresh, refresh) || other.refresh == refresh) &&
            (identical(other.user, user) || other.user == user) &&
            (identical(other.applicant, applicant) ||
                other.applicant == applicant));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, access, refresh, user, applicant);

  @override
  String toString() {
    return 'SignInResponseDto(access: $access, refresh: $refresh, user: $user, applicant: $applicant)';
  }
}

/// @nodoc
abstract mixin class $SignInResponseDtoCopyWith<$Res> {
  factory $SignInResponseDtoCopyWith(
          SignInResponseDto value, $Res Function(SignInResponseDto) _then) =
      _$SignInResponseDtoCopyWithImpl;
  @useResult
  $Res call(
      {String access,
      String refresh,
      AuthUserDto user,
      AuthApplicantDto? applicant});

  $AuthUserDtoCopyWith<$Res> get user;
  $AuthApplicantDtoCopyWith<$Res>? get applicant;
}

/// @nodoc
class _$SignInResponseDtoCopyWithImpl<$Res>
    implements $SignInResponseDtoCopyWith<$Res> {
  _$SignInResponseDtoCopyWithImpl(this._self, this._then);

  final SignInResponseDto _self;
  final $Res Function(SignInResponseDto) _then;

  /// Create a copy of SignInResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? access = null,
    Object? refresh = null,
    Object? user = null,
    Object? applicant = freezed,
  }) {
    return _then(_self.copyWith(
      access: null == access
          ? _self.access
          : access // ignore: cast_nullable_to_non_nullable
              as String,
      refresh: null == refresh
          ? _self.refresh
          : refresh // ignore: cast_nullable_to_non_nullable
              as String,
      user: null == user
          ? _self.user
          : user // ignore: cast_nullable_to_non_nullable
              as AuthUserDto,
      applicant: freezed == applicant
          ? _self.applicant
          : applicant // ignore: cast_nullable_to_non_nullable
              as AuthApplicantDto?,
    ));
  }

  /// Create a copy of SignInResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $AuthUserDtoCopyWith<$Res> get user {
    return $AuthUserDtoCopyWith<$Res>(_self.user, (value) {
      return _then(_self.copyWith(user: value));
    });
  }

  /// Create a copy of SignInResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $AuthApplicantDtoCopyWith<$Res>? get applicant {
    if (_self.applicant == null) {
      return null;
    }

    return $AuthApplicantDtoCopyWith<$Res>(_self.applicant!, (value) {
      return _then(_self.copyWith(applicant: value));
    });
  }
}

/// Adds pattern-matching-related methods to [SignInResponseDto].
extension SignInResponseDtoPatterns on SignInResponseDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_SignInResponseDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SignInResponseDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_SignInResponseDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SignInResponseDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_SignInResponseDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SignInResponseDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(String access, String refresh, AuthUserDto user,
            AuthApplicantDto? applicant)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _SignInResponseDto() when $default != null:
        return $default(
            _that.access, _that.refresh, _that.user, _that.applicant);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(String access, String refresh, AuthUserDto user,
            AuthApplicantDto? applicant)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SignInResponseDto():
        return $default(
            _that.access, _that.refresh, _that.user, _that.applicant);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(String access, String refresh, AuthUserDto user,
            AuthApplicantDto? applicant)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _SignInResponseDto() when $default != null:
        return $default(
            _that.access, _that.refresh, _that.user, _that.applicant);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _SignInResponseDto implements SignInResponseDto {
  const _SignInResponseDto(
      {required this.access,
      required this.refresh,
      required this.user,
      this.applicant});
  factory _SignInResponseDto.fromJson(Map<String, dynamic> json) =>
      _$SignInResponseDtoFromJson(json);

  @override
  final String access;
  @override
  final String refresh;
  @override
  final AuthUserDto user;
  @override
  final AuthApplicantDto? applicant;

  /// Create a copy of SignInResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$SignInResponseDtoCopyWith<_SignInResponseDto> get copyWith =>
      __$SignInResponseDtoCopyWithImpl<_SignInResponseDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$SignInResponseDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _SignInResponseDto &&
            (identical(other.access, access) || other.access == access) &&
            (identical(other.refresh, refresh) || other.refresh == refresh) &&
            (identical(other.user, user) || other.user == user) &&
            (identical(other.applicant, applicant) ||
                other.applicant == applicant));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode =>
      Object.hash(runtimeType, access, refresh, user, applicant);

  @override
  String toString() {
    return 'SignInResponseDto(access: $access, refresh: $refresh, user: $user, applicant: $applicant)';
  }
}

/// @nodoc
abstract mixin class _$SignInResponseDtoCopyWith<$Res>
    implements $SignInResponseDtoCopyWith<$Res> {
  factory _$SignInResponseDtoCopyWith(
          _SignInResponseDto value, $Res Function(_SignInResponseDto) _then) =
      __$SignInResponseDtoCopyWithImpl;
  @override
  @useResult
  $Res call(
      {String access,
      String refresh,
      AuthUserDto user,
      AuthApplicantDto? applicant});

  @override
  $AuthUserDtoCopyWith<$Res> get user;
  @override
  $AuthApplicantDtoCopyWith<$Res>? get applicant;
}

/// @nodoc
class __$SignInResponseDtoCopyWithImpl<$Res>
    implements _$SignInResponseDtoCopyWith<$Res> {
  __$SignInResponseDtoCopyWithImpl(this._self, this._then);

  final _SignInResponseDto _self;
  final $Res Function(_SignInResponseDto) _then;

  /// Create a copy of SignInResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? access = null,
    Object? refresh = null,
    Object? user = null,
    Object? applicant = freezed,
  }) {
    return _then(_SignInResponseDto(
      access: null == access
          ? _self.access
          : access // ignore: cast_nullable_to_non_nullable
              as String,
      refresh: null == refresh
          ? _self.refresh
          : refresh // ignore: cast_nullable_to_non_nullable
              as String,
      user: null == user
          ? _self.user
          : user // ignore: cast_nullable_to_non_nullable
              as AuthUserDto,
      applicant: freezed == applicant
          ? _self.applicant
          : applicant // ignore: cast_nullable_to_non_nullable
              as AuthApplicantDto?,
    ));
  }

  /// Create a copy of SignInResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $AuthUserDtoCopyWith<$Res> get user {
    return $AuthUserDtoCopyWith<$Res>(_self.user, (value) {
      return _then(_self.copyWith(user: value));
    });
  }

  /// Create a copy of SignInResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $AuthApplicantDtoCopyWith<$Res>? get applicant {
    if (_self.applicant == null) {
      return null;
    }

    return $AuthApplicantDtoCopyWith<$Res>(_self.applicant!, (value) {
      return _then(_self.copyWith(applicant: value));
    });
  }
}

/// @nodoc
mixin _$RefreshResponseDto {
  String get access;
  String get refresh;

  /// Create a copy of RefreshResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $RefreshResponseDtoCopyWith<RefreshResponseDto> get copyWith =>
      _$RefreshResponseDtoCopyWithImpl<RefreshResponseDto>(
          this as RefreshResponseDto, _$identity);

  /// Serializes this RefreshResponseDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is RefreshResponseDto &&
            (identical(other.access, access) || other.access == access) &&
            (identical(other.refresh, refresh) || other.refresh == refresh));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, access, refresh);

  @override
  String toString() {
    return 'RefreshResponseDto(access: $access, refresh: $refresh)';
  }
}

/// @nodoc
abstract mixin class $RefreshResponseDtoCopyWith<$Res> {
  factory $RefreshResponseDtoCopyWith(
          RefreshResponseDto value, $Res Function(RefreshResponseDto) _then) =
      _$RefreshResponseDtoCopyWithImpl;
  @useResult
  $Res call({String access, String refresh});
}

/// @nodoc
class _$RefreshResponseDtoCopyWithImpl<$Res>
    implements $RefreshResponseDtoCopyWith<$Res> {
  _$RefreshResponseDtoCopyWithImpl(this._self, this._then);

  final RefreshResponseDto _self;
  final $Res Function(RefreshResponseDto) _then;

  /// Create a copy of RefreshResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? access = null,
    Object? refresh = null,
  }) {
    return _then(_self.copyWith(
      access: null == access
          ? _self.access
          : access // ignore: cast_nullable_to_non_nullable
              as String,
      refresh: null == refresh
          ? _self.refresh
          : refresh // ignore: cast_nullable_to_non_nullable
              as String,
    ));
  }
}

/// Adds pattern-matching-related methods to [RefreshResponseDto].
extension RefreshResponseDtoPatterns on RefreshResponseDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_RefreshResponseDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _RefreshResponseDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_RefreshResponseDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _RefreshResponseDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_RefreshResponseDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _RefreshResponseDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(String access, String refresh)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _RefreshResponseDto() when $default != null:
        return $default(_that.access, _that.refresh);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(String access, String refresh) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _RefreshResponseDto():
        return $default(_that.access, _that.refresh);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(String access, String refresh)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _RefreshResponseDto() when $default != null:
        return $default(_that.access, _that.refresh);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _RefreshResponseDto implements RefreshResponseDto {
  const _RefreshResponseDto({required this.access, required this.refresh});
  factory _RefreshResponseDto.fromJson(Map<String, dynamic> json) =>
      _$RefreshResponseDtoFromJson(json);

  @override
  final String access;
  @override
  final String refresh;

  /// Create a copy of RefreshResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$RefreshResponseDtoCopyWith<_RefreshResponseDto> get copyWith =>
      __$RefreshResponseDtoCopyWithImpl<_RefreshResponseDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$RefreshResponseDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _RefreshResponseDto &&
            (identical(other.access, access) || other.access == access) &&
            (identical(other.refresh, refresh) || other.refresh == refresh));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, access, refresh);

  @override
  String toString() {
    return 'RefreshResponseDto(access: $access, refresh: $refresh)';
  }
}

/// @nodoc
abstract mixin class _$RefreshResponseDtoCopyWith<$Res>
    implements $RefreshResponseDtoCopyWith<$Res> {
  factory _$RefreshResponseDtoCopyWith(
          _RefreshResponseDto value, $Res Function(_RefreshResponseDto) _then) =
      __$RefreshResponseDtoCopyWithImpl;
  @override
  @useResult
  $Res call({String access, String refresh});
}

/// @nodoc
class __$RefreshResponseDtoCopyWithImpl<$Res>
    implements _$RefreshResponseDtoCopyWith<$Res> {
  __$RefreshResponseDtoCopyWithImpl(this._self, this._then);

  final _RefreshResponseDto _self;
  final $Res Function(_RefreshResponseDto) _then;

  /// Create a copy of RefreshResponseDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? access = null,
    Object? refresh = null,
  }) {
    return _then(_RefreshResponseDto(
      access: null == access
          ? _self.access
          : access // ignore: cast_nullable_to_non_nullable
              as String,
      refresh: null == refresh
          ? _self.refresh
          : refresh // ignore: cast_nullable_to_non_nullable
              as String,
    ));
  }
}

/// @nodoc
mixin _$AuthUserDto {
  String get id;
  String get email;
  String get role;
  String? get displayName;

  /// Create a copy of AuthUserDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $AuthUserDtoCopyWith<AuthUserDto> get copyWith =>
      _$AuthUserDtoCopyWithImpl<AuthUserDto>(this as AuthUserDto, _$identity);

  /// Serializes this AuthUserDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is AuthUserDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.email, email) || other.email == email) &&
            (identical(other.role, role) || other.role == role) &&
            (identical(other.displayName, displayName) ||
                other.displayName == displayName));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, email, role, displayName);

  @override
  String toString() {
    return 'AuthUserDto(id: $id, email: $email, role: $role, displayName: $displayName)';
  }
}

/// @nodoc
abstract mixin class $AuthUserDtoCopyWith<$Res> {
  factory $AuthUserDtoCopyWith(
          AuthUserDto value, $Res Function(AuthUserDto) _then) =
      _$AuthUserDtoCopyWithImpl;
  @useResult
  $Res call({String id, String email, String role, String? displayName});
}

/// @nodoc
class _$AuthUserDtoCopyWithImpl<$Res> implements $AuthUserDtoCopyWith<$Res> {
  _$AuthUserDtoCopyWithImpl(this._self, this._then);

  final AuthUserDto _self;
  final $Res Function(AuthUserDto) _then;

  /// Create a copy of AuthUserDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? email = null,
    Object? role = null,
    Object? displayName = freezed,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      email: null == email
          ? _self.email
          : email // ignore: cast_nullable_to_non_nullable
              as String,
      role: null == role
          ? _self.role
          : role // ignore: cast_nullable_to_non_nullable
              as String,
      displayName: freezed == displayName
          ? _self.displayName
          : displayName // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// Adds pattern-matching-related methods to [AuthUserDto].
extension AuthUserDtoPatterns on AuthUserDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_AuthUserDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _AuthUserDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_AuthUserDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _AuthUserDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_AuthUserDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _AuthUserDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(String id, String email, String role, String? displayName)?
        $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _AuthUserDto() when $default != null:
        return $default(_that.id, _that.email, _that.role, _that.displayName);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(String id, String email, String role, String? displayName)
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _AuthUserDto():
        return $default(_that.id, _that.email, _that.role, _that.displayName);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(
            String id, String email, String role, String? displayName)?
        $default,
  ) {
    final _that = this;
    switch (_that) {
      case _AuthUserDto() when $default != null:
        return $default(_that.id, _that.email, _that.role, _that.displayName);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _AuthUserDto implements AuthUserDto {
  const _AuthUserDto(
      {required this.id,
      required this.email,
      required this.role,
      this.displayName});
  factory _AuthUserDto.fromJson(Map<String, dynamic> json) =>
      _$AuthUserDtoFromJson(json);

  @override
  final String id;
  @override
  final String email;
  @override
  final String role;
  @override
  final String? displayName;

  /// Create a copy of AuthUserDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$AuthUserDtoCopyWith<_AuthUserDto> get copyWith =>
      __$AuthUserDtoCopyWithImpl<_AuthUserDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$AuthUserDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _AuthUserDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.email, email) || other.email == email) &&
            (identical(other.role, role) || other.role == role) &&
            (identical(other.displayName, displayName) ||
                other.displayName == displayName));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, email, role, displayName);

  @override
  String toString() {
    return 'AuthUserDto(id: $id, email: $email, role: $role, displayName: $displayName)';
  }
}

/// @nodoc
abstract mixin class _$AuthUserDtoCopyWith<$Res>
    implements $AuthUserDtoCopyWith<$Res> {
  factory _$AuthUserDtoCopyWith(
          _AuthUserDto value, $Res Function(_AuthUserDto) _then) =
      __$AuthUserDtoCopyWithImpl;
  @override
  @useResult
  $Res call({String id, String email, String role, String? displayName});
}

/// @nodoc
class __$AuthUserDtoCopyWithImpl<$Res> implements _$AuthUserDtoCopyWith<$Res> {
  __$AuthUserDtoCopyWithImpl(this._self, this._then);

  final _AuthUserDto _self;
  final $Res Function(_AuthUserDto) _then;

  /// Create a copy of AuthUserDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? email = null,
    Object? role = null,
    Object? displayName = freezed,
  }) {
    return _then(_AuthUserDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      email: null == email
          ? _self.email
          : email // ignore: cast_nullable_to_non_nullable
              as String,
      role: null == role
          ? _self.role
          : role // ignore: cast_nullable_to_non_nullable
              as String,
      displayName: freezed == displayName
          ? _self.displayName
          : displayName // ignore: cast_nullable_to_non_nullable
              as String?,
    ));
  }
}

/// @nodoc
mixin _$AuthApplicantDto {
  String get id;
  String get userId;

  /// Create a copy of AuthApplicantDto
  /// with the given fields replaced by the non-null parameter values.
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  $AuthApplicantDtoCopyWith<AuthApplicantDto> get copyWith =>
      _$AuthApplicantDtoCopyWithImpl<AuthApplicantDto>(
          this as AuthApplicantDto, _$identity);

  /// Serializes this AuthApplicantDto to a JSON map.
  Map<String, dynamic> toJson();

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is AuthApplicantDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.userId, userId) || other.userId == userId));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, userId);

  @override
  String toString() {
    return 'AuthApplicantDto(id: $id, userId: $userId)';
  }
}

/// @nodoc
abstract mixin class $AuthApplicantDtoCopyWith<$Res> {
  factory $AuthApplicantDtoCopyWith(
          AuthApplicantDto value, $Res Function(AuthApplicantDto) _then) =
      _$AuthApplicantDtoCopyWithImpl;
  @useResult
  $Res call({String id, String userId});
}

/// @nodoc
class _$AuthApplicantDtoCopyWithImpl<$Res>
    implements $AuthApplicantDtoCopyWith<$Res> {
  _$AuthApplicantDtoCopyWithImpl(this._self, this._then);

  final AuthApplicantDto _self;
  final $Res Function(AuthApplicantDto) _then;

  /// Create a copy of AuthApplicantDto
  /// with the given fields replaced by the non-null parameter values.
  @pragma('vm:prefer-inline')
  @override
  $Res call({
    Object? id = null,
    Object? userId = null,
  }) {
    return _then(_self.copyWith(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      userId: null == userId
          ? _self.userId
          : userId // ignore: cast_nullable_to_non_nullable
              as String,
    ));
  }
}

/// Adds pattern-matching-related methods to [AuthApplicantDto].
extension AuthApplicantDtoPatterns on AuthApplicantDto {
  /// A variant of `map` that fallback to returning `orElse`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeMap<TResult extends Object?>(
    TResult Function(_AuthApplicantDto value)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _AuthApplicantDto() when $default != null:
        return $default(_that);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// Callbacks receives the raw object, upcasted.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case final Subclass2 value:
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult map<TResult extends Object?>(
    TResult Function(_AuthApplicantDto value) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _AuthApplicantDto():
        return $default(_that);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `map` that fallback to returning `null`.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case final Subclass value:
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? mapOrNull<TResult extends Object?>(
    TResult? Function(_AuthApplicantDto value)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _AuthApplicantDto() when $default != null:
        return $default(_that);
      case _:
        return null;
    }
  }

  /// A variant of `when` that fallback to an `orElse` callback.
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return orElse();
  /// }
  /// ```

  @optionalTypeArgs
  TResult maybeWhen<TResult extends Object?>(
    TResult Function(String id, String userId)? $default, {
    required TResult orElse(),
  }) {
    final _that = this;
    switch (_that) {
      case _AuthApplicantDto() when $default != null:
        return $default(_that.id, _that.userId);
      case _:
        return orElse();
    }
  }

  /// A `switch`-like method, using callbacks.
  ///
  /// As opposed to `map`, this offers destructuring.
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case Subclass2(:final field2):
  ///     return ...;
  /// }
  /// ```

  @optionalTypeArgs
  TResult when<TResult extends Object?>(
    TResult Function(String id, String userId) $default,
  ) {
    final _that = this;
    switch (_that) {
      case _AuthApplicantDto():
        return $default(_that.id, _that.userId);
      case _:
        throw StateError('Unexpected subclass');
    }
  }

  /// A variant of `when` that fallback to returning `null`
  ///
  /// It is equivalent to doing:
  /// ```dart
  /// switch (sealedClass) {
  ///   case Subclass(:final field):
  ///     return ...;
  ///   case _:
  ///     return null;
  /// }
  /// ```

  @optionalTypeArgs
  TResult? whenOrNull<TResult extends Object?>(
    TResult? Function(String id, String userId)? $default,
  ) {
    final _that = this;
    switch (_that) {
      case _AuthApplicantDto() when $default != null:
        return $default(_that.id, _that.userId);
      case _:
        return null;
    }
  }
}

/// @nodoc
@JsonSerializable()
class _AuthApplicantDto implements AuthApplicantDto {
  const _AuthApplicantDto({required this.id, required this.userId});
  factory _AuthApplicantDto.fromJson(Map<String, dynamic> json) =>
      _$AuthApplicantDtoFromJson(json);

  @override
  final String id;
  @override
  final String userId;

  /// Create a copy of AuthApplicantDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @JsonKey(includeFromJson: false, includeToJson: false)
  @pragma('vm:prefer-inline')
  _$AuthApplicantDtoCopyWith<_AuthApplicantDto> get copyWith =>
      __$AuthApplicantDtoCopyWithImpl<_AuthApplicantDto>(this, _$identity);

  @override
  Map<String, dynamic> toJson() {
    return _$AuthApplicantDtoToJson(
      this,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        (other.runtimeType == runtimeType &&
            other is _AuthApplicantDto &&
            (identical(other.id, id) || other.id == id) &&
            (identical(other.userId, userId) || other.userId == userId));
  }

  @JsonKey(includeFromJson: false, includeToJson: false)
  @override
  int get hashCode => Object.hash(runtimeType, id, userId);

  @override
  String toString() {
    return 'AuthApplicantDto(id: $id, userId: $userId)';
  }
}

/// @nodoc
abstract mixin class _$AuthApplicantDtoCopyWith<$Res>
    implements $AuthApplicantDtoCopyWith<$Res> {
  factory _$AuthApplicantDtoCopyWith(
          _AuthApplicantDto value, $Res Function(_AuthApplicantDto) _then) =
      __$AuthApplicantDtoCopyWithImpl;
  @override
  @useResult
  $Res call({String id, String userId});
}

/// @nodoc
class __$AuthApplicantDtoCopyWithImpl<$Res>
    implements _$AuthApplicantDtoCopyWith<$Res> {
  __$AuthApplicantDtoCopyWithImpl(this._self, this._then);

  final _AuthApplicantDto _self;
  final $Res Function(_AuthApplicantDto) _then;

  /// Create a copy of AuthApplicantDto
  /// with the given fields replaced by the non-null parameter values.
  @override
  @pragma('vm:prefer-inline')
  $Res call({
    Object? id = null,
    Object? userId = null,
  }) {
    return _then(_AuthApplicantDto(
      id: null == id
          ? _self.id
          : id // ignore: cast_nullable_to_non_nullable
              as String,
      userId: null == userId
          ? _self.userId
          : userId // ignore: cast_nullable_to_non_nullable
              as String,
    ));
  }
}

// dart format on
