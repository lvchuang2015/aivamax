---
title: "How to Prevent Duplicate Actions Using the JarveePro Scheduler"
source_url: "https://blog.jarveepro.com/knowledge/JarveePro-Scheduler/How-to-Prevent-Duplicate-Actions-Using-the-JarveePro-Scheduler/5571"
category: "knowledge"
fetched_at: "2026-05-29T15:10:29+00:00"
status_code: 200
content_hash: "bceddc1523301ff4c3b3bba07c6682cdc3fcbc9f"
tags: ["jarveepro", "jarveepro/knowledge"]
---

# How to Prevent Duplicate Actions Using the JarveePro Scheduler

Source: [https://blog.jarveepro.com/knowledge/JarveePro-Scheduler/How-to-Prevent-Duplicate-Actions-Using-the-JarveePro-Scheduler/5571](https://blog.jarveepro.com/knowledge/JarveePro-Scheduler/How-to-Prevent-Duplicate-Actions-Using-the-JarveePro-Scheduler/5571)

Category: `knowledge`

## Summary

How to Prevent Duplicate Actions Using the JarveePro Scheduler

## Headings

- How to Prevent Duplicate Actions Using the JarveePro Scheduler
- Introduction
- Why Duplicate Actions Happen
- Understanding the New JarveePro Scheduler Logic
- Critical Option: Task Record Cleanup
- How the “Clean Up Completed Task Records” Option Works
- ✅ When ENABLED
- ❌ When DISABLED (Recommended)
- Correct Scheduler Setup to Prevent Duplicate Actions
- Step-by-Step Configuration
- Important Clarification: Scheduler vs Content Explorer
- Common Use Cases & Best Practices
- Facebook Friend Requests
- Instagram Comment Campaigns
- High-Volume Campaigns
- Summary

## Content

How to Prevent Duplicate Actions Using the JarveePro Scheduler

2026-01-12

Introduction

Duplicate actions are one of the most common issues users face when running scheduled campaigns in JarveePro—especially when looping tasks like

Facebook friend requests

Instagram comments

, or

content-based actions

Many users assume the scheduler should “remember” where it left off. In reality,

the new JarveePro Scheduler works based on task records

, not sequence memory.

This article explains

why duplicates happen

, how the

new scheduler logic works

, and

exactly how to configure it

to prevent repeated actions.

Why Duplicate Actions Happen

JarveePro does

not create duplicate actions by default

Duplicates only occur when the user enables

Reset/Cleanup

mode, which is designed for looping campaigns such as story views or video watches.

By default:

The scheduler restarts the campaign

Previously completed targets won't be reprocessed

This behavior is

intentional

, not a bug

The key lies in

task record handling

Understanding the New JarveePro Scheduler Logic

In the new scheduler UI, each campaign run creates

task records

These records determine:

Which actions were completed

Which targets were already processed

Whether the campaign starts fresh or continues logically

Critical Option: Task Record Cleanup

Inside the scheduler settings, you’ll see this option:

☐ Clean up completed task records when starting a task

This checkbox controls duplicate behavior.

How the “Clean Up Completed Task Records” Option Works

✅ When ENABLED

All previous task records are deleted

Campaign starts from the beginning

Duplicates WILL happen

Best for:

Engagement farming

Repeating actions on purpose

Evergreen campaigns

❌ When DISABLED (Recommended)

Completed targets are remembered

Scheduler skips already-processed users

Campaign continues naturally

Duplicates are PREVENTED

Facebook friend requests

DM campaigns

Lead-based workflows

Sequential target lists (A → B → C)

To prevent duplicates, this option must remain UNCHECKED

Correct Scheduler Setup to Prevent Duplicate Actions

Step-by-Step Configuration

Open

Campaign → Scheduler

Select:

Schedule Type:

Loop Run

DO NOT check

❌ Clean up completed task records when starting a task

Set your interval (hours or minutes)

Enable Scheduler

That’s it.

JarveePro will now

remember completed actions

and avoid duplicates.

Important Clarification: Scheduler vs Content Explorer

⚠️ The scheduler

only applies to campaigns

, not Content Explorer searches.

Content Explorer:

Uses platform rules

May re-scan content

Has separate duplicate controls

Scheduler:

Controls campaign execution

Relies on task records

Trying to apply scheduler logic to Content Explorer will

not work

Common Use Cases & Best Practices

Facebook Friend Requests

Upload target profile URLs once

Disable task record cleanup

Scheduler continues target-by-target without repeats

Instagram Comment Campaigns

Works best with

Content Aware Comment

Avoid aggressive loop intervals

Use delays

High-Volume Campaigns

Use VPS with sufficient RAM/CPU

Avoid excessive browser instances

Scheduler logic remains consistent regardless of scale

Summary

Duplicate actions are caused by task record cleanup

JarveePro Scheduler relies on task history

Disable cleanup to prevent duplicates

Scheduler applies only to campaigns, not Content Explorer

Proper configuration ensures smooth, sequential execution

## Extracted Links

- https://blog.jarveepro.com/Home/Blog
- https://blog.jarveepro.com/Home/KnowledgeBaseList
- https://blog.jarveepro.com/knowledge/JarveePro-Scheduler/How-to-Prevent-Duplicate-Actions-Using-the-JarveePro-Scheduler/5571
- https://twitter.com/share?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Scheduler%2FHow-to-Prevent-Duplicate-Actions-Using-the-JarveePro-Scheduler%2F5571
- https://www.facebook.com/jarveeproadmin
- https://www.facebook.com/sharer/sharer.php?u=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Scheduler%2FHow-to-Prevent-Duplicate-Actions-Using-the-JarveePro-Scheduler%2F5571
- https://www.jarveepro.com/
- https://www.jarveepro.com/all-features.html
- https://www.jarveepro.com/contact-us.html
- https://www.jarveepro.com/contact.html
- https://www.jarveepro.com/discord-features.html
- https://www.jarveepro.com/facebook-features.html
- https://www.jarveepro.com/get-now.html
- https://www.jarveepro.com/instagram-features.html
- https://www.jarveepro.com/linkedIn-features.html
- https://www.jarveepro.com/pinterest-features.html
- https://www.jarveepro.com/pricing.html
- https://www.jarveepro.com/reddit-features.html
- https://www.jarveepro.com/tiktok-features.html
- https://www.jarveepro.com/tumblr-features.html
- https://www.jarveepro.com/twitter-features.html
- https://www.jarveepro.com/videos-tutorials.html
- https://www.jarveepro.com/whatsapp-features.html
- https://www.jarveepro.com/youtube-features.html
- https://www.pinterest.com/pin/create/button/?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Scheduler%2FHow-to-Prevent-Duplicate-Actions-Using-the-JarveePro-Scheduler%2F5571
