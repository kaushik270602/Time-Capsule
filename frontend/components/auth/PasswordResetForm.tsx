"use client";

import React, { useState } from "react";
import Link from "next/link";
import { authApi } from "@/lib/api";
import FormInput from "@/components/ui/FormInput";

export default function PasswordResetForm({ token }: { token?: string }) {
  const isResetMode = !!token;
  const [email, setEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (isResetMode) {
      if (!newPassword) errs.newPassword = "Password is required";
      else if (newPassword.length < 8)
        errs.newPassword = "Password must be at least 8 characters";
      else if (!/[A-Z]/.test(newPassword) || !/[a-z]/.test(newPassword) || !/\d/.test(newPassword))
        errs.newPassword = "Password must include uppercase, lowercase, and a number";
      if (newPassword !== confirmPassword)
        errs.confirmPassword = "Passwords do not match";
    } else {
      if (!email) errs.email = "Email is required";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    try {
      if (isResetMode) {
        await authApi.resetPassword(token!, newPassword);
      } else {
        await authApi.requestPasswordReset(email);
      }
      setSuccess(true);
    } catch (err: any) {
      setErrors({ form: err.response?.data?.detail || "Something went wrong. Please try again." });
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="text-center p-6">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
          <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" strokeWidth="2" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
          </svg>
        </div>
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          {isResetMode ? "Password updated" : "Check your email"}
        </h2>
        <p className="text-gray-600 mb-4">
          {isResetMode
            ? "Your password has been reset successfully."
            : "If an account exists with that email, we sent a reset link."}
        </p>
        <Link href="/login" className="text-indigo-600 hover:text-indigo-500 font-medium">
          Back to login
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <h2 className="text-2xl font-bold text-gray-900 text-center">
        {isResetMode ? "Set new password" : "Reset your password"}
      </h2>
      {!isResetMode && (
        <p className="text-sm text-gray-600 text-center">
          Enter your email and we&apos;ll send you a reset link.
        </p>
      )}
      {errors.form && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700" role="alert">
          {errors.form}
        </div>
      )}
      {isResetMode ? (
        <>
          <FormInput
            id="new-password"
            label="New Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            error={errors.newPassword}
            autoComplete="new-password"
            required
          />
          <FormInput
            id="confirm-password"
            label="Confirm Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            error={errors.confirmPassword}
            autoComplete="new-password"
            required
          />
        </>
      ) : (
        <FormInput
          id="reset-email"
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
          autoComplete="email"
          required
        />
      )}
      <button
        type="submit"
        disabled={submitting}
        className="w-full py-2 px-4 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {submitting
          ? isResetMode ? "Updating..." : "Sending..."
          : isResetMode ? "Update password" : "Send reset link"}
      </button>
      <p className="text-center text-sm text-gray-600">
        <Link href="/login" className="text-indigo-600 hover:text-indigo-500 font-medium">
          Back to login
        </Link>
      </p>
    </form>
  );
}
