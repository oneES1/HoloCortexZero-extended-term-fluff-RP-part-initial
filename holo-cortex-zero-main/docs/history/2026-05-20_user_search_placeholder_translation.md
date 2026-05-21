# User Search Placeholder Translation

## Problem

The User management search box placeholder did not match the intended field scope.

## Evidence

- `frontend/src/pages/user-manager/index.tsx` renders the search box with `t('search.placeholder')`.
- The Chinese locale showed `搜索用户名或QQ号`.
- The English locale showed `Search username or QQ number`.

## Change

- Chinese placeholder: `搜索用户昵称或ID`
- English placeholder: `Search user nickname or ID`

## Impact

- UI text only.
- No search API, filtering logic, pagination, or user data behavior changed.

## Verification

- Validate user-manager locale JSON files.
- Run frontend production build.
