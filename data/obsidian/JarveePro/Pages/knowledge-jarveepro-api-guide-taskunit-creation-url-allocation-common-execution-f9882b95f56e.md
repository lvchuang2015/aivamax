---
title: "JarveePro API Guide: TaskUnit Creation, URL Allocation & Common Execution Errors"
source_url: "https://blog.jarveepro.com/knowledge/JarveePro-Developer-API/JarveePro-API-Guide-TaskUnit-Creation,-URL-Allocation-Common-Execution-Errors/6761"
category: "knowledge"
fetched_at: "2026-05-29T15:10:27+00:00"
status_code: 200
content_hash: "97524e6db03ae0810dceafc0c4461444c9a8fdbc"
tags: ["jarveepro", "jarveepro/knowledge"]
---

# JarveePro API Guide: TaskUnit Creation, URL Allocation & Common Execution Errors

Source: [https://blog.jarveepro.com/knowledge/JarveePro-Developer-API/JarveePro-API-Guide-TaskUnit-Creation,-URL-Allocation-Common-Execution-Errors/6761](https://blog.jarveepro.com/knowledge/JarveePro-Developer-API/JarveePro-API-Guide-TaskUnit-Creation,-URL-Allocation-Common-Execution-Errors/6761)

Category: `knowledge`

## Summary

JarveePro API Guide: TaskUnit Creation, URL Allocation & Common Execution Errors

## Headings

- JarveePro API Guide: TaskUnit Creation, URL Allocation & Common Execution Errors
- Introduction
- 1. Why Your Task Creates Only 1 TaskUnit (Even with 50–100 Accounts)
- Key Rule
- Why This Happens
- 2. The Real Control: URL Allocation Parameters
- UseNoData (Highest Priority)
- AccountUseNum
- UseNum
- 3. Fix for “Only 1 TaskUnit” Problem
- Option A (Recommended)
- Option B
- 4. Understanding the “Value cannot be null” Error
- Example: LikePost
- Hidden Cause
- 5. TaskSettingJson: When It’s Required (and When It’s Not)
- LikePost
- ViewStoriesReels
- 6. Is ViewStoriesReels the Correct TaskType for Reels?
- 7. Why You See “Open Browser Error” or “Browser Closed”
- Common Causes
- Important Insight
- 8. Why Only 1 Browser Opens for 50 Accounts
- 9. Advanced Controls for Task Distribution
- MainUseParam
- Reallocation
- MainKey
- 10. Key Takeaways (What Actually Matters)
- Summary

## Content

JarveePro API Guide: TaskUnit Creation, URL Allocation & Common Execution Errors

2026-04-20

Introduction

When using the JarveePro API for Instagram automation, many users assume that:

More accounts = more parallel execution units.”

That’s not always true.

Recent cases show confusion around:

Tasks collapsing into a single TaskUnit

“Value cannot be null” errors

“Open Browser Error” and “Browser closed” issues

Incorrect parameter distribution across accounts

This guide breaks down exactly how

TaskUnits are generated

, how

URL allocation works

, and why tasks may fail even when the API request is technically valid.

1. Why Your Task Creates Only 1 TaskUnit (Even with 50–100 Accounts)

This is

not a bug

JarveePro builds TaskUnits based on

parameter distribution rules

, not simply the number of accounts.

Key Rule

TaskUnits are primarily determined by the

MainKey parameter

(for Instagram, usually

Url

).

So:

10 accounts + 1 URL → 1 TaskUnit

1 account + 10 URLs → 1 TaskUnit

10 accounts + 10 URLs → multiple TaskUnits (depending on allocation settings)

Why This Happens

The system groups execution by

parameter units

, not accounts.

If your task only has:

"Url": ["single_url"]

Then all accounts are grouped into

one execution unit

, even if 100 accounts are provided.

2. The Real Control: URL Allocation Parameters

Inside your request:

"Parameter": {

"Url": {

"Parameters": [...],

"UseNoData": false,

"AccountUseNum": 1,

"UseNum": 100

These fields control everything:

UseNoData (Highest Priority)

true

→ URL can be reused infinitely

Every account can use the same URL

Overrides all other allocation rules

AccountUseNum

How many times a single URL can be used

Default =

(this is where many setups break)

If you have:

1 URL

50 accounts

AccountUseNum = 1

→ Only

1 account can use that URL

, others fail or collapse

UseNum

Total allowed usage count across the task

Does NOT control TaskUnit splitting directly

3. Fix for “Only 1 TaskUnit” Problem

If your goal is:

“1 URL → many accounts → multiple executions”

You must use:

Option A (Recommended)

"UseNoData": true

This allows:

Unlimited reuse of URL

Proper distribution across all accounts

Option B

"AccountUseNum": 50

Manually match it to account count.

4. Understanding the “Value cannot be null” Error

Error:

Instagram EX: Value cannot be null. Parameter name: value

This is

not random

. It means:

A required parameter defined by the TaskType is missing or null.

Example: LikePost

Requires ONLY:

Url

(MainKey)

If:

URL is empty

URL allocation fails

URL not assigned to a TaskUnit

→ This error appears

Hidden Cause

When allocation rules block URLs from being assigned (e.g.,

AccountUseNum=1

with many accounts), some TaskUnits end up with

no usable parameter

, triggering this exception.

5. TaskSettingJson: When It’s Required (and When It’s Not)

LikePost

Does

NOT

require

TaskSettingJson

ViewStoriesReels

❌ DOES require settings

Correct format:

"TaskSettingJson": {

"WatchTimeMin": 10,

"WatchTimeMax": 20,

"WatchTimeFull": true

If missing → task may fail or behave unpredictably.

6. Is ViewStoriesReels the Correct TaskType for Reels?

Yes—but incomplete usage is the problem.

You must include:

Url

InstagramViewStoriesReelsSetting

Without settings → execution is invalid.

7. Why You See “Open Browser Error” or “Browser Closed”

This is

separate from API structure

It happens at runtime due to:

Common Causes

VPS Mode disabled (required for browser execution in many setups)

Browser environment not initialized

Fingerprint/session issues

Resource limits (trying to open 50 browsers at once)

Only 1 thread allowed → only 1 browser opens

Important Insight

API success ≠ runtime success

Your logs already confirm:

API layer working

Task creation working

Failure happens during execution

8. Why Only 1 Browser Opens for 50 Accounts

This usually means:

Thread/concurrency limits are set to 1

Or system resources restrict scaling

Or accounts are grouped into 1 TaskUnit (most likely in your case)

Remember:

TaskUnit = execution container

If you only have 1 TaskUnit → only 1 browser instance is needed.

9. Advanced Controls for Task Distribution

These fields influence execution behavior:

MainUseParam

Whether main parameter drives execution logic

Reallocation

"Reallocation": true

Forces redistribution of TaskUnits during execution

MainKey

Defines the parameter used for grouping (usually

Url

10. Key Takeaways (What Actually Matters)

JarveePro distributes tasks based on

parameters, not accounts

is the

core driver

for Instagram tasks

Wrong allocation settings → tasks collapse or fail

“Value cannot be null” = parameter assignment failure

“Open Browser Error” = runtime/environment issue, not API

ViewStoriesReels requires

extra settings

, unlike LikePost

Summary

Most API issues are not caused by incorrect request formats—but by

misunderstanding how JarveePro builds execution units internally

If you remember just one thing:

Accounts don’t create TaskUnits—parameters do.

Once you fix parameter allocation (especially

UseNoData

and

AccountUseNum

), most “mysterious” failures disappear.

## Extracted Links

- https://blog.jarveepro.com/Home/Blog
- https://blog.jarveepro.com/Home/KnowledgeBaseList
- https://blog.jarveepro.com/knowledge/JarveePro-Developer-API/JarveePro-API-Guide-TaskUnit-Creation,-URL-Allocation-Common-Execution-Errors/6761
- https://twitter.com/share?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Developer-API%2FJarveePro-API-Guide-TaskUnit-Creation%2C-URL-Allocation-Common-Execution-Errors%2F6761
- https://www.facebook.com/jarveeproadmin
- https://www.facebook.com/sharer/sharer.php?u=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Developer-API%2FJarveePro-API-Guide-TaskUnit-Creation%2C-URL-Allocation-Common-Execution-Errors%2F6761
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
- https://www.pinterest.com/pin/create/button/?url=http%3A%2F%2Fblog.jarveepro.com%2Fknowledge%2FJarveePro-Developer-API%2FJarveePro-API-Guide-TaskUnit-Creation%2C-URL-Allocation-Common-Execution-Errors%2F6761
