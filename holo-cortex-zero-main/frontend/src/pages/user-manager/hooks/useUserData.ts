import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getUserList, 
  deleteUser, 
  banUser, 
  setPreventTrigger, 
  User
} from '../../../services/api/user-manager';

interface Pagination {
  page: number;
  page_size: number;
}

export const useUserData = (searchTerm: string) => {
  const queryClient = useQueryClient();
  const [pagination, setPagination] = useState<Pagination>({ page: 1, page_size: 10 });

  // 获取用户列表
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['users', pagination.page, pagination.page_size, searchTerm],
    queryFn: () => getUserList({
      page: pagination.page,
      page_size: pagination.page_size,
      search: searchTerm,
      sort_by: 'id',
      sort_order: 'desc'
    }),
    refetchOnWindowFocus: false,
    staleTime: 0,
  });

  // 删除用户
  const deleteUserMutation = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    }
  });

  // 封禁/解封用户
  const banUserMutation = useMutation({
    mutationFn: ({ id, banUntil }: { id: number; banUntil: string | null }) => banUser(id, banUntil),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    }
  });

  // 设置触发权限
  const setPreventTriggerMutation = useMutation({
    mutationFn: ({ id, preventTriggerUntil }: { id: number; preventTriggerUntil: string | null }) => 
      setPreventTrigger(id, preventTriggerUntil),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    }
  });

  return {
    users: (data?.data?.items || []) as User[],
    total: data?.data?.total || 0,
    isLoading,
    pagination,
    setPagination,
    deleteUser: deleteUserMutation.mutateAsync,
    banUser: banUserMutation.mutateAsync,
    setPreventTrigger: setPreventTriggerMutation.mutateAsync,
    refetch
  };
};
