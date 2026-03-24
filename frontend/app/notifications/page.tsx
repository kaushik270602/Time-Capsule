"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  notificationApi,
  NotificationResponse as NotifResponse,
} from "@/lib/api";

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<NotifResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetch = async () => {
      try {
        const { data } = await notificationApi.list();
        setNotifications(data.notifications);
      } catch {
        setError("Failed to load notifications.");
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, []);

  const handleMarkRead = async (id: number) => {
    try {
      await notificationApi.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch {
      // ignore – user can retry
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Notifications</h1>
        <div className="text-gray-400 text-sm">Loading notifications…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto py-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-6">Notifications</h1>
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm">
          {error}
        </div>
      </div>
    );
  }

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="max-w-3xl mx-auto py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
          <p className="mt-1 text-sm text-gray-500">
            {unreadCount > 0
              ? `${unreadCount} unread notification${unreadCount !== 1 ? "s" : ""}`
              : "All caught up!"}
          </p>
        </div>
      </div>

      {notifications.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
          <p className="text-gray-400 text-sm">No notifications yet.</p>
          <Link
            href="/dashboard"
            className="mt-3 inline-block text-sm text-indigo-600 hover:text-indigo-800 font-medium"
          >
            Back to Dashboard
          </Link>
        </div>
      ) : (
        <ul className="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
          {notifications.map((n) => (
            <li
              key={n.id}
              className={`flex items-start gap-4 px-5 py-4 ${
                n.is_read ? "opacity-60" : ""
              }`}
            >
              <div className="pt-1">
                {!n.is_read ? (
                  <span className="block h-2.5 w-2.5 rounded-full bg-indigo-500" />
                ) : (
                  <span className="block h-2.5 w-2.5 rounded-full bg-gray-300" />
                )}
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-800">{n.message}</p>
                <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
                  <time dateTime={n.created_at}>
                    {new Date(n.created_at).toLocaleString()}
                  </time>
                  <Link
                    href={`/capsules/${n.capsule_id}`}
                    className="text-indigo-600 hover:text-indigo-800 font-medium"
                  >
                    View capsule
                  </Link>
                </div>
              </div>

              {!n.is_read && (
                <button
                  onClick={() => handleMarkRead(n.id)}
                  className="flex-shrink-0 text-xs text-indigo-600 hover:text-indigo-800 font-medium px-2 py-1 rounded hover:bg-indigo-50 transition-colors"
                >
                  Mark read
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
