import Ionicons from '@expo/vector-icons/Ionicons';
import { useQuery } from '@tanstack/react-query';
import { Image } from 'expo-image';
import { openBrowserAsync } from 'expo-web-browser';
import React, { useState } from 'react';
import { FlatList, Modal, Pressable, ScrollView, View, useWindowDimensions } from 'react-native';
import { AppText, Card } from '@/components/ui';
import { Radius, Spacing, useColors } from '@/constants/theme';
import { uploadsApi, type AttachmentView } from '@/lib/api';
import { formatAccuracy, mapsLink, photoAgeNote } from '@/lib/gallery';
import { formatDateTime } from './format';

/** Photos (and videos) attached to a ticket: horizontal thumbnails, tap for a full-screen viewer. */
export function TicketGallery({ ticketRef, reportedAt }: { ticketRef: string; reportedAt: string }) {
  const colors = useColors();
  const { width, height } = useWindowDimensions();
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const { data } = useQuery({
    queryKey: ['ticket', ticketRef, 'attachments'],
    queryFn: async () => (await uploadsApi.forTicket(ticketRef)).data,
  });

  if (!data || data.length === 0) return null;
  const ageNote = photoAgeNote(data.map((item) => item.captured_at), reportedAt);

  return (
    <Card>
      <AppText variant="heading">Photos</AppText>
      {ageNote ? <AppText variant="muted">{ageNote}</AppText> : null}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: Spacing.sm }}>
        {data.map((item, index) => (
          <Pressable key={item.id} accessibilityRole="imagebutton" accessibilityLabel={`Open ${item.file_name}`} onPress={() => setOpenIndex(index)}>
            <View style={{ width: 110, height: 110, borderRadius: Radius.md, overflow: 'hidden', backgroundColor: colors.secondary }}>
              {item.thumb_url ? <Image source={{ uri: item.thumb_url }} style={{ flex: 1 }} contentFit="cover" /> : null}
              {item.kind === 'video' ? (
                <View style={{ position: 'absolute', inset: 0, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name="play-circle" size={36} color="#FFFFFF" />
                </View>
              ) : null}
            </View>
          </Pressable>
        ))}
      </ScrollView>

      <Modal visible={openIndex !== null} animationType="fade" onRequestClose={() => setOpenIndex(null)} presentationStyle="fullScreen">
        <View style={{ flex: 1, backgroundColor: '#000000' }}>
          {openIndex !== null ? (
            <FlatList
              data={data}
              horizontal
              pagingEnabled
              initialScrollIndex={openIndex}
              getItemLayout={(_, index) => ({ length: width, offset: width * index, index })}
              keyExtractor={(item) => item.id}
              showsHorizontalScrollIndicator={false}
              renderItem={({ item }) => <Slide item={item} width={width} height={height} />}
            />
          ) : null}
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Close"
            onPress={() => setOpenIndex(null)}
            hitSlop={12}
            style={{ position: 'absolute', top: 56, right: Spacing.lg, padding: Spacing.sm, borderRadius: Radius.pill, backgroundColor: 'rgba(0,0,0,0.6)' }}>
            <Ionicons name="close" size={26} color="#FFFFFF" />
          </Pressable>
        </View>
      </Modal>
    </Card>
  );
}

function Slide({ item, width, height }: { item: AttachmentView; width: number; height: number }) {
  const facts: string[] = [];
  const taken = formatDateTime(item.captured_at);
  if (taken) facts.push(`Taken ${taken}`);
  const accuracy = formatAccuracy(item.gps_accuracy_m);
  const hasGps = item.gps_lat !== null && item.gps_lng !== null;
  return (
    <View style={{ width, height, justifyContent: 'center' }}>
      <Image
        source={{ uri: item.view_url ?? item.thumb_url ?? undefined }}
        style={{ width, height: height * 0.7 }}
        contentFit="contain"
        accessibilityLabel={item.file_name}
      />
      <View style={{ position: 'absolute', left: Spacing.lg, right: Spacing.lg, bottom: 48, gap: Spacing.sm }}>
        {facts.map((fact) => (
          <AppText key={fact} variant="muted" style={{ color: '#FFFFFF' }}>{fact}</AppText>
        ))}
        {hasGps ? (
          <Pressable onPress={() => openBrowserAsync(mapsLink(item.gps_lat as number, item.gps_lng as number))}>
            <AppText variant="muted" style={{ color: '#93C5FD' }}>Open the spot in Maps{accuracy ? ` (${accuracy})` : ''}</AppText>
          </Pressable>
        ) : null}
        {item.kind === 'video' && item.view_url ? (
          <Pressable onPress={() => openBrowserAsync(item.view_url as string)}>
            <AppText variant="muted" style={{ color: '#93C5FD' }}>Play video</AppText>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}
